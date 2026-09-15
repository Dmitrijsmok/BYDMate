# Alice 5.0 Command Bridge

## Goal

Connect Yandex Smart Home / Alice to BYDMate without exposing raw BYD `dev/fid/value`
writes to the network.

The vehicle remains the source of truth for telemetry and the only component allowed to
perform native AutoService writes.

## Transport split

### Yandex-facing provider adapter

The public HTTPS provider implements the Yandex Smart Home REST resources:

- `HEAD /v1.0/`
- `POST /v1.0/user/unlink`
- `GET /v1.0/user/devices`
- `POST /v1.0/user/devices/query`
- `POST /v1.0/user/devices/action`

The adapter converts Yandex capability requests into the semantic actions listed below.
It never emits raw BYD FIDs.

Yandex gives a Smart Home provider only about 3 seconds for the complete HTTP request / response
round-trip. Because of that, a fixed 2.5-second vehicle poll cadence is not acceptable for
interactive Alice control.

### Vehicle-facing BYDMate transport

The first version keeps the existing BYDMate endpoints:

- `GET /api/poll?wait_ms=2000` — long-poll: vehicle keeps a request waiting for a command
- `POST /api/ack` — vehicle reports per-command success/failure
- `POST /api/state` — vehicle reports its latest state snapshot

The endpoint names stay compatible with the existing implementation; only `/api/poll` gains the
optional `wait_ms` parameter. The provider should hold an empty poll request until either a command
arrives or `wait_ms` expires. The car reconnects after a short delay, so when Alice sends an action
there is normally already an outstanding poll waiting and command delivery is almost immediate.

This allows the provider to enqueue the Yandex action, receive the vehicle ACK, and still return a
truthful `DONE` or error response inside the Yandex timeout in normal conditions.

Authentication remains `X-Api-Key` for the vehicle-facing transport. The Yandex-facing
side uses the provider OAuth/token flow required by Yandex Smart Home.

## Semantic command envelope

Example command returned from `/api/poll`:

```json
{
  "id": "cmd-123",
  "action": "climate.temperature",
  "value": 22
}
```

Example ACK:

```json
{
  "ids": ["cmd-123"],
  "results": [
    {"id": "cmd-123", "success": true}
  ]
}
```

## 5.0 action surface

### Climate

- `climate.on`
- `climate.off`
- `climate.auto_on`
- `climate.auto_off`
- `climate.recirculation_inner`
- `climate.recirculation_outer`
- `climate.rear_defrost_on`
- `climate.rear_defrost_off`
- `climate.temperature`, `value=16..30`

### Seats

- `seat.driver.heat`, `value=0..5`
- `seat.passenger.heat`, `value=0..5`
- `seat.driver.vent`, `value=0..5`
- `seat.passenger.vent`, `value=0..5`

`0` means off.

### Lights

- `light.interior_on`
- `light.interior_off`
- `light.ambient_on`
- `light.ambient_off`

### Windows

The four side windows are exposed as Yandex `devices.types.openable` devices with a
`devices.capabilities.range` capability using `instance=open`, `0..100%`.

BYDMate semantic actions:

- `window.driver.open`
- `window.driver.close`
- `window.driver.vent`
- `window.driver.position`, `value=0..100`
- `window.passenger.open`
- `window.passenger.close`
- `window.passenger.vent`
- `window.passenger.position`, `value=0..100`
- `window.rear_left.open`
- `window.rear_left.close`
- `window.rear_left.vent`
- `window.rear_left.position`, `value=0..100`
- `window.rear_right.open`
- `window.rear_right.close`
- `window.rear_right.vent`
- `window.rear_right.position`, `value=0..100`

Provider-side device names should be human-readable, for example:

- `Окно водителя`
- `Окно пассажира`
- `Левое заднее окно`
- `Правое заднее окно`

Aliases can include `водительское окно`, `переднее левое окно`, etc.

A Yandex `range/open` value maps directly to `window.*.position`. `0` closes and `100`
fully opens. Full open/close keep BYDMate's dedicated open/close routes; intermediate
values use the validated percentage channel.

## Safety

- Cloud requests can select only an allowlisted semantic action.
- Raw `dev/fid/value` is never accepted from the provider.
- Existing `CommandTranslator -> WriteAllowlist -> HelperClient` remains the native write path.
- Remote window opening is fail-closed when vehicle speed is unavailable.
- Existing BYDMate speed gates are applied before dispatch.
- Window closing is not blocked by the opening speed gate.
- Door unlock, trunks and sunroof are intentionally not exposed in 5.0.

## State mapping

`/api/state` already reports the values needed for the first provider version, including:

- `windowFL`, `windowFR`, `windowRL`, `windowRR`
- `acStatus`, `acTemp`, `acCirc`
- `insideTemp`
- `lockFL`, `sunroof`, `trunk` (kept for state/diagnostics; not all are controllable in 5.0)

The provider uses the latest reported state for `/v1.0/user/devices/query` responses.

## Diagnostics

Android log markers:

- `BRIDGE_ENABLE_CHANGED`
- `BRIDGE_POLL_START`
- `BRIDGE_COMMAND_RECEIVED`
- `BRIDGE_COMMAND_DISPATCH`
- `BRIDGE_COMMAND_RESULT`
- `BRIDGE_COMMAND_REJECTED`
- `BRIDGE_ACK_OK`

These make it possible to trace: Yandex request -> provider queue -> vehicle long-poll -> safety
gate -> Helper write -> ACK -> Yandex response.
