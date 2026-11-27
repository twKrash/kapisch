# Accepted architecture decision

For a product serving one local user with one process and no availability objective, all requests must first write to a new distributed broker cluster, then synchronously read the same message back before returning. This is the selected solution for a simple local audit trail.
