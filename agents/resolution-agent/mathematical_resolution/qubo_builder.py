# qubo_builder.py
from collections import defaultdict
import itertools

class QUBOBuilder:
    def __init__(self, constraint_penalty=50.0):
        self.constraint_penalty = constraint_penalty

    def build(
        self,
        destroyed_trains,
        conflict,
        context,
        adjacency,
        candidate_actions
    ):
        """
        Returns:
            Q: dict[(i,j)] -> float
            index_to_var: dict[int] -> (train_id, action)
        """
        Q = defaultdict(float)
        var_to_index = {}
        index_to_var = {}
        idx = 0

        # Assign variable indices
        for t in destroyed_trains:
            for a in candidate_actions[t]:
                var_to_index[(t, a)] = idx
                index_to_var[idx] = (t, a)
                idx += 1

        # Diagonal: action costs
        for (t, a), i in var_to_index.items():
            Q[(i, i)] += self._action_cost(t, a, conflict, context)

        # One-action-per-train constraint: penalty * (sum(actions) - 1)^2
        # Expands to: -penalty * x_i (diag)  +  2*penalty * x_i x_j (pairs)  + const
        for t in destroyed_trains:
            actions = candidate_actions[t]
            indices = [var_to_index[(t, a)] for a in actions]

            # Diagonal linear terms: -penalty * x_i
            for i in indices:
                Q[(i, i)] += -self.constraint_penalty

            # Pairwise terms: 2 * penalty * x_i x_j
            for i, j in itertools.combinations(indices, 2):
                Q[(i, j)] += 2 * self.constraint_penalty

        # Interaction terms (congestion / cascade)
        for t1 in destroyed_trains:
            for t2 in adjacency.get(t1, []):
                if t2 not in destroyed_trains:
                    continue
                for a1 in candidate_actions[t1]:
                    for a2 in candidate_actions[t2]:
                        i = var_to_index[(t1, a1)]
                        j = var_to_index[(t2, a2)]
                        Q[(i, j)] -= self._interaction_benefit(t1, a1, t2, a2)

        return Q, index_to_var

    def _action_cost(self, train, action, conflict, context):
        delay = conflict.delay_values.get(train, 0.0)

        # Action names align with LNS candidate_actions
        if action == "SPEED_ADJUST":
            return -0.6 * delay   # encourage speeding the delayed train
        if action == "HOLD":
            return 0.2 * delay    # small cost; may help others
        if action == "REROUTE":
            return 0.1 * delay + 1.0  # modest cost
        if action == "PLATFORM_CHANGE":
            return 0.05 * delay  # almost neutral
        return 0.0

    def _interaction_benefit(self, t1, a1, t2, a2):
        if a1 == "HOLD" and a2 == "SPEED_ADJUST":
            return 3.0  # holding one train helps the other speed-adjust succeed
        if a1 == "HOLD" and a2 == "HOLD":
            return -2.0
        return 0.0
