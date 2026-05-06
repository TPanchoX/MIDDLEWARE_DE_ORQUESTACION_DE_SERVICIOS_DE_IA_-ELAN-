from time import perf_counter


class ProbabilityAggregator:
    def aggregate(
        self,
        window_probabilities: list[list[float]],
        window_frame_indices: list[list[int]],
        total_frames: int,
    ) -> tuple[list[float], int]:
        started_at = perf_counter()
        sums = [0.0 for _ in range(total_frames)]
        counts = [0 for _ in range(total_frames)]

        for probabilities, frame_indices in zip(window_probabilities, window_frame_indices):
            for probability, frame_index in zip(probabilities, frame_indices):
                if 0 <= frame_index < total_frames:
                    sums[frame_index] += float(probability)
                    counts[frame_index] += 1

        aggregated = [
            sums[index] / counts[index] if counts[index] else 0.0
            for index in range(total_frames)
        ]
        return aggregated, self._elapsed_ms(started_at)

    @staticmethod
    def _elapsed_ms(started_at: float) -> int:
        return max(1, int(round((perf_counter() - started_at) * 1000)))


probability_aggregator = ProbabilityAggregator()
