import os
import midi

def getFileList(current_dir, filters=None):
	_all_files = []

	for (path, directories, files) in os.walk(current_dir):
		for file_name in files:
			ext = os.path.splitext(file_name)[-1]
			if filters is None or ext in filters:
				_all_files.append(os.path.join(path, file_name))

	return _all_files


if __name__ == "__main__":

	histogram = [[0]*12 for i in range(2)]

	all_files = getFileList('data', ['.mid', '.midi'])

	for file_name in all_files:
		try:
			pattern = midi.read_midifile(file_name)
		except Exception as ex:
			if len(ex.args) >= 2:
				if ex.args[1] == b'RIFF':
					print("ERROR(RMID format): {0}".format(file_name))
					continue
				elif ex.args[1] == b'':
					print("ERROR(Empty file): {0}".format(file_name))
					continue

			print("ERROR({1}): {0}".format(file_name, ex.args[0]))
			continue

		pattern.make_ticks_abs()

		tracks = midi.Track(pattern)

		resolution = pattern.resolution
		bpm = 0
		max_channel = -1
		beats = 0
		beat_type = 0

		for track in tracks:

			incomplete = {}
			incomplete_2nd = {}

			for event in track:
				if isinstance(event, midi.events.ProgramChangeEvent):
					if event.channel == 9:
						break

				if isinstance(event, midi.events.TimeSignatureEvent):
					# data=[4, 2, 24, 8]
					if beats <= 0:
						beats = event.data[0]
						if beat_type <= 0:
							beat_type = 1 << event.data[1]

				if isinstance(event, midi.events.SetTempoEvent):
					tempo_in_msec = (event.data[0] & 0xFF) << 16 | (event.data[1] & 0xFF) << 8 | (event.data[2] & 0xFF)
					if tempo_in_msec > 0:
						bpm = 1000000 * 60 // tempo_in_msec

				if isinstance(event, midi.events.KeySignatureEvent):
					num_sharp = event.data[0]
					num_sharp = num_sharp if num_sharp < 0x80 else num_sharp - 256
					is_major_scale = (event.data[1] == 0)

					# TODO(ykahn) temporary
					if not (num_sharp == 0 and is_major_scale):
						break
				
				if isinstance(event, midi.events.NoteOnEvent) and event.velocity > 0:

					# FIXME(ykahn)
					if beats == 0:
						beats = 4
						beat_type = 4

					time_stamp = event.tick / resolution / beats
					key = event.channel << 8 | event.pitch
					if not key in incomplete:
						incomplete[key] = [time_stamp, event.velocity]
					elif not key in incomplete_2nd:
						incomplete_2nd[key] = [time_stamp, event.velocity]
					else:
						print("[WARNING] Too many intersections")

				if isinstance(event, midi.events.NoteOffEvent) or (isinstance(event, midi.events.NoteOnEvent) and event.velocity == 0):

					# FIXME(ykahn)
					if beats == 0:
						beats = 4
						beat_type = 4

					time_stamp = event.tick / resolution / beats
					key = event.channel << 8 | event.pitch
					if key in incomplete_2nd:
						duration = (time_stamp - incomplete_2nd[key][0])
						histogram[0 if is_major_scale else 1][(key & 0xFF) % 12] += duration

						if duration < 0:
							print("DEBUG POINT!!")

						del incomplete_2nd[key]
					elif key in incomplete:
						duration = (time_stamp - incomplete[key][0])
						histogram[0 if is_major_scale else 1][(key & 0xFF) % 12] += duration

						if duration < 0:
							print("DEBUG POINT!!")

						del incomplete[key]
					else:
						print("[WARNING] Cannot find NoteOn before NoteOff")

		print("File: {0}".format(file_name))
		# print("    RESOLUTION = {0}".format(resolution))
		# print("    BPM = {0}".format(bpm))
		# print("    NUM_SHARPS = {0}".format(num_sharp))
		# print("    SCALE = {0}".format('Major' if not is_major_scale else 'Minor'))

	print('DONE')
