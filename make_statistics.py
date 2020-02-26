import os
import midi

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

from functools import reduce
from typing import List, Tuple


def getFileList(current_dir: str, filters: [] = None) -> []:
	_all_files = []

	for (path, directories, files) in os.walk(current_dir):
		for file_name in files:
			ext = os.path.splitext(file_name)[-1]
			if filters is None or ext in filters:
				_all_files.append(os.path.join(path, file_name))

	return _all_files


def getOffsetBySharps(num_sharps: int, is_major_scale: bool) -> int:
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
		'minor': [9, 4, 11, 6, 1, 8, 3, 10, 8, 3, 10, 5, 0, 7, 2]
	}

	if abs(num_sharps) <= 7:
		return OFFSET_TABLE['major' if is_major_scale else 'minor'][num_sharps]
	else:
		return 0


def getKeySignatureBySharps(num_sharps: int, is_major_scale: bool) -> str:
	OFFSET_TABLE = {
		'major': ['C', 'G', 'D', 'A', 'E', 'B', 'F#','C#', 'Cb', 'Gb', 'Db', 'Ab', 'Eb', 'Bb', 'F'],
		'minor': ['A', 'E', 'B', 'F#', 'C#', 'G#', 'D#', 'A#', 'Ab', 'Eb', 'Bb', 'F', 'C', 'G', 'D' ]
	}

	if abs(num_sharps) <= 7:
		return OFFSET_TABLE['major' if is_major_scale else 'minor'][num_sharps]
	else:
		return '??'


class MidiNote:
	pitch: int
	time_beg: float
	time_end: float
	velocity: int

	def __init__(self, pitch: int, time_beg: float, time_end: float, velocity: int):
		self.pitch = pitch
		self.time_beg = time_beg
		self.time_end = time_end
		self.velocity = velocity


class MidiStruct:

	def __init__(self, pattern: midi.Pattern):
		pattern.make_ticks_abs()

		self.tracks = midi.Track(pattern)
		self.resolution = pattern.resolution
		self.bpm = 100
		self.max_channel = -1
		self.beats = 4
		self.beat_type = 4
		self.num_sharps = 0
		self.is_major_scale = True
		self.scale_verified = False

		_complete_bits = 0

		for track in self.tracks:
			for event in track:

				# beats and beat type
				if (_complete_bits & 0x01) == 0 and isinstance(event, midi.events.TimeSignatureEvent):
					# TODO(ykahn): Time signature can be changed while playing

					self.beats = event.numerator
					self.beat_type = event.denominator
					_complete_bits |= 0x01

				# tempo
				if (_complete_bits & 0x02) == 0 and isinstance(event, midi.events.SetTempoEvent):
					# TODO(ykahn): Tempo can be changed while playing

					self.bpm = int(event.bpm)
					_complete_bits |= 0x02

				# key signature and scale
				if (_complete_bits & 0x04) == 0 and isinstance(event, midi.events.KeySignatureEvent):
					# TODO(ykahn): Key signature can be changed while playing

					self.num_sharps = event.alternatives
					self.is_major_scale = (event.minor == 0)
					self.scale_verified = abs(self.num_sharps) <= 7
					_complete_bits |= 0x04

				if isinstance(event, midi.events.NoteOnEvent):
					if self.max_channel < event.channel:
						self.max_channel = event.channel

	def getFullNotes(self) -> Tuple[List[List[MidiNote]], int]:
		""" Get full notes for each channel in MIDI

		:param
		:return: (Result[channel][note_sequnece]: MidiNote, offset from C)
		:rtype: Tuple[List[List[MidiNote]], int]
		"""

		noduvels = [[] for i in range(self.max_channel + 1)]

		for track in self.tracks:

			# FIXME(ykahn): It should be created using List.
			incomplete = {}
			incomplete_2nd = {}

			for event in track:
				is_note_on = isinstance(event, midi.events.NoteOnEvent) and event.velocity > 0
				is_note_off = isinstance(event, midi.events.NoteOffEvent) or (isinstance(event, midi.events.NoteOnEvent) and event.velocity == 0)

				# Skip percussion channels
				if (is_note_on or is_note_off) and event.channel == 9:
					continue

				if is_note_on:
					time_stamp = event.tick / self.resolution / self.beats
					key = event.channel << 8 | event.pitch
					if not key in incomplete:
						incomplete[key] = [time_stamp, event.velocity]
					elif not key in incomplete_2nd:
						incomplete_2nd[key] = [time_stamp, event.velocity]
					else:
						print('[WARNING] Too many intersections')

				if is_note_off:
					time_stamp = event.tick / self.resolution / self.beats
					key = event.channel << 8 | event.pitch
					if key in incomplete_2nd:
						duration = (time_stamp - incomplete_2nd[key][0])
						if duration >= 0:
							noduvels[event.channel].append(MidiNote(event.pitch, incomplete_2nd[key][0], time_stamp, incomplete_2nd[key][1]))
						else:
							print('DEBUG POINT!!')

						del incomplete_2nd[key]
					elif key in incomplete:
						duration = (time_stamp - incomplete[key][0])
						if duration >= 0:
							noduvels[event.channel].append(MidiNote(event.pitch, incomplete[key][0], time_stamp, incomplete[key][1]))
						else:
							print('DEBUG POINT!!')

						del incomplete[key]
					else:
						print('[WARNING] Cannot find NoteOn before NoteOff')

		return noduvels, getOffsetBySharps(self.num_sharps, self.is_major_scale)


if __name__ == '__main__':

	histogram = [[0]*12 for i in range(2)]

	all_files = getFileList('data', ['.mid', '.midi'])

	for file_name in all_files:

		try:
			pattern = midi.read_midifile(file_name)
		except Exception as ex:
			if len(ex.args) >= 2:
				if ex.args[1] == b'RIFF':
					print('ERROR(RMID format): {0}'.format(file_name))
					continue
				elif ex.args[1] == b'':
					print('ERROR(Empty file): {0}'.format(file_name))
					continue

			print('ERROR({1}): {0}'.format(file_name, ex.args[0]))
			continue

		midi_feature = MidiStruct(pattern)
		midi_notes, note_offset = midi_feature.getFullNotes()

		histogram_scale = histogram[0 if midi_feature.is_major_scale else 1]

		for notes_in_channel in midi_notes:
			for note in notes_in_channel:
				duration = note.time_end - note.time_beg
				if note.pitch > note_offset and duration > 0:
					histogram_scale[(note.pitch- note_offset) % 12] += duration

		if midi_feature.scale_verified:
			print('File: {0} - {1}({2})'.format(file_name, 'major' if midi_feature.is_major_scale else 'minor', getKeySignatureBySharps(midi_feature.num_sharps, midi_feature.is_major_scale)))
		else:
			print(f'File: {file_name}')

	# Result
	# histogram = [[15683.887337963031, 3093.279027777861, 10735.73865740727, 4439.18699074093, 14634.81780092495, 9808.816550925509, 3388.6425868056467, 15203.483067129102, 5248.000920139239, 11730.83645254645, 4044.7510532408332, 8810.800283564655], [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]]
	# print(histogram)

	# Normalize
	normalized = []
	for octave in histogram:
		sum = reduce(lambda a, b: a + b, octave)
		normalized.append(list(map(lambda val: (val / sum) if sum > 0 else 0, octave)))

	# print(normalized)
	print('DONE')
	

	x_label = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'Ab', 'A', 'Bb', 'B']
	x_index = np.arange(len(x_label))

	plt.bar(x_index, list(map(lambda val: val*100, normalized[0])))
	
	plt.title('The stabilities of the 12 tones in the major key', fontsize=14)
	plt.xlabel('Notes', fontsize=12)
	plt.ylabel('Percentage(%)', fontsize=12)

	plt.gca().yaxis.set_major_formatter(PercentFormatter())

	plt.xticks(x_index, x_label, fontsize=10)

	plt.show()
