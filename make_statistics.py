import os
import midi

def getFileList(current_dir: str, filters: [] = None) -> []:
	_all_files = []

	for (path, directories, files) in os.walk(current_dir):
		for file_name in files:
			ext = os.path.splitext(file_name)[-1]
			if filters is None or ext in filters:
				_all_files.append(os.path.join(path, file_name))

	return _all_files

def getOffsetBySharps(sharps: int, is_major_scale: bool) -> int:
	''' in case of the major scale
	Cb	Db	Eb	Fb	Gb	Ab	Bb	7 flats
	Gb	Ab	Bb	Cb	Db	Eb	F	6 flats
	Db	Eb	F	Gb	Ab	Bb	C	5 flats
	Ab	Bb	C	Db	Eb	F	G	4 flats
	Eb	F	G	Ab	Bb	C	D	3 flats
	Bb	C	D	Eb	F	G	A	2 flats
	F	G	A	Bb	C	D	E	1 flat
	C	D	E	F	G	A	B	no flats or sharps
	G	A	B	C	D	E	F#	1 sharp
	D	E	F#	G	A	B	C#	2 sharps
	A	B	C#	D	E	F#	G#	3 sharps
	E	F#	G#	A	B	C#	D#	4 sharps
	B	C#	D#	E	F#	G#	A#	5 sharps
	F#	G#	A#	B	C#	D#	E#	6 sharps
	C#	D#	E#	F#	G#	A#	B#	7 sharps	
	'''
	''' in case of the major scale
	Ab	Bb	Cb	Db	Eb	Fb	Gb	7 flats
	Eb	F	Gb	Ab	Bb	Cb	Db	6 flats
	Bb	C	Db	Eb	F	Gb	Ab	5 flats
	F	G	Ab	Bb	C	Db	Eb	4 flats
	C	D	Eb	F	G	Ab	Bb	3 flats
	G	A	Bb	C	D	Eb	F	2 flats
	D	E	F	G	A	Bb	C	1 flat
	A	B	C	D	E	F	G	no flats or sharps
	E	F#	G	A	B	C	D	1 sharp
	B	C#	D	E	F#	G	A	2 sharps
	F#	G#	A	B	C#	D	E	3 sharps
	C#	D#	E	F#	G#	A	B	4 sharps
	G#	A#	B	C#	D#	E	F#	5 sharps
	D#	E#	F#	G#	A#	B	C#	6 sharps
	A#	B#	C#	D#	E#	F#	G#	7 sharps
	'''
	OFFSET_TABLE = {
		'major': [0, 7, 2, 9, 4, 11, 6, 1, 11, 6, 1, 8, 3, 10, 5],
		# XXX(ykahn)
		'minor': [0, 7, 2, 9, 4, 11, 6, 1, 11, 6, 1, 8, 3, 10, 5]
	}

	if abs(sharps) <= 7:
		return OFFSET_TABLE['major' if is_major_scale else 'minor'][sharps]
	else:
		return 0


if __name__ == "__main__":

	histogram = [[0]*12 for i in range(2)]

	all_files = getFileList('_data', ['.mid', '.midi'])

	for file_name in all_files:

		cannot_process = False

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
		num_sharp = 0
		is_major_scale = True

		for track in tracks:

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

		if beats == 0:
			beats = 4
			beat_type = 4

		if resolution <= 0:
			cannot_process = True

		# test for each scale
		# if num_sharp == 0 and is_major_scale:
		# 	cannot_process = True

		if cannot_process:
			break

		note_offset = getOffsetBySharps(num_sharp, is_major_scale)

		for track in tracks:

			incomplete = {}
			incomplete_2nd = {}

			for event in track:
				
				if isinstance(event, midi.events.NoteOnEvent) and event.velocity > 0:
					time_stamp = event.tick / resolution / beats
					key = event.channel << 8 | event.pitch
					if not key in incomplete:
						incomplete[key] = [time_stamp, event.velocity]
					elif not key in incomplete_2nd:
						incomplete_2nd[key] = [time_stamp, event.velocity]
					else:
						print("[WARNING] Too many intersections")

				if isinstance(event, midi.events.NoteOffEvent) or (isinstance(event, midi.events.NoteOnEvent) and event.velocity == 0):
					time_stamp = event.tick / resolution / beats
					key = event.channel << 8 | event.pitch
					if key in incomplete_2nd:
						duration = (time_stamp - incomplete_2nd[key][0])
						histogram[0 if is_major_scale else 1][((key & 0xFF) - note_offset) % 12] += duration

						if duration < 0:
							print("DEBUG POINT!!")

						del incomplete_2nd[key]
					elif key in incomplete:
						duration = (time_stamp - incomplete[key][0])
						histogram[0 if is_major_scale else 1][((key & 0xFF) - note_offset) % 12] += duration

						if duration < 0:
							print("DEBUG POINT!!")

						del incomplete[key]
					else:
						print("[WARNING] Cannot find NoteOn before NoteOff")

			if cannot_process:
				break

		print("File: {0}".format(file_name))
		# print("    RESOLUTION = {0}".format(resolution))
		# print("    BPM = {0}".format(bpm))
		# print("    NUM_SHARPS = {0}".format(num_sharp))
		# print("    SCALE = {0}".format('Major' if not is_major_scale else 'Minor'))

	for octave in histogram:
		sum = 1
		for note in octave:
			sum += note
		
		if sum > 0:
			for i in range(len(octave)):
				octave[i] = octave[i] / sum

	print('DONE')
	print(histogram)
