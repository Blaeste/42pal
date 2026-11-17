"""The wait after a failed grademe: none at first, then longer and longer.

Like the rest of the core, this module never prints: the shell shows the
waits and refuses a grademe that comes too early.
"""

from dataclasses import dataclass

@dataclass(frozen=True)
class RetryPolicy:
	"""How long to wait after each failure, in minutes.

	minutes[0] is the wait after the 1st failure (0: the first retry is
	free), minutes[1] after the 2nd, and so on; past the end, the last one
	repeats.
	"""
	minutes: tuple[int, ...]

	def wait_after(self, failures):
		"""Return the seconds to wait after `failures` failures (0 for none)."""
		if failures == 0:
			return 0
		index = min(failures, len(self.minutes)) - 1
		return self.minutes[index] * 60
