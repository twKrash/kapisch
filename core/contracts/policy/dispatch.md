# Dispatch policy

Dispatch only an admissible role, stage, tier, effect, and capability combination under static core policy. Logical tier is semantic; adapter-local provider/model/profile choices cannot reduce it or change authority. Repository writes require enforced write capability; unknown or advisory capability is insufficient. External-write and destructive effects remain unsupported absent a separately approved safe protocol.

The controller is the single writer. For durable work, persist a stable operation ID, exact request, and `dispatch-uncertain` state before invoking an adapter. A missing receipt does not prove dispatch did not occur. Never repeat an unresolved operation; reconcile only that exact operation when the adapter can observe it safely.
