# Spec Amendment 1 — the product shape: engine room + thin devices

*2026-11-01, Casey's framing, recorded the day Slice 1 started.*

The spec describes a platform. Casey named the **product**:

> A Thor is the back-end superpower for any thin device — a phone
> becomes the IO, cameras included. And "product" means a thing
> his technicians can install and service. All open source, easy
> to use.

Consequences, binding on the build order:

1. **Thin devices are first-class citizens, not demo props.** The
   phone-as-camera is the reference IO node: zero-install on the
   device beyond a commodity streaming app, discovered on the LAN
   by the platform, perceived by the Thor. Tablets, old phones,
   Orin-class boxes and browsers are the same citizen at different
   sizes. The platform's API surface is designed for devices that
   bring a sensor and a screen and nothing else.
2. **Installability is a feature with an acceptance test.** Slice 1
   ships with a technician's install guide and a dry-run-first
   installer (`slice1/install/` in the working tree). A build that
   only Muse can install is not the product. Serviceability means
   plain-language health, named faults with symptom → check → fix,
   and a service card a technician can work from without the repo.
3. **Open source is the distribution.** The repo's graduation
   (private → public, Casey's call) is the product launch channel:
   technicians install from the public repo, and the docs a
   stranger reads are the docs the technician uses. The
   stranger-test standard from wave 2 applies to every slice.
4. **The customer is a household; the channel is a technician.**
   Design reviews must pass both readers: the person who lives
   with the feed, and the person who gets called when it breaks.
5. **One wiring model for the technician (Casey, same day).** The
   uniformity is not an aesthetic — it is the service model. If
   everything is a cell with power and IO attached, the technician
   learns ONE way to wire anything together: a camera, a voice, a
   model, a stream. No per-device folklore, no special cases to
   memorise. The complexity lives inside the cells.
6. **Agents are the optimisers in the background.** What lives
   inside a cell — the actual logic of the application — is
   optimised continuously by coding agents, and the scoreboard for
   that optimisation is the human experience of the system: the
   feed's trustworthiness, the presence at the table, the
   technician's ten-minute install. Humans wire cells and judge
   experience; agents grind the internals. A technician never
   needs to know which model or scheduler a cell runs this month.
7. **Converters are the platform's problem (Casey, same day).** The
   technician thinks like the person who wires a building: what
   connects where, and which protocol the connection speaks. Where
   two things don't natively speak — a camera's stream into the
   ledger's text, a model's dialect into a verdict — the back end
   provides the converter, maintained by the agents. The
   technician's craft is wiring, endpoints and protocols; what a
   converter does inside is one more cell interior he never opens.
   A connection that needs a human to translate is a missing
   converter, and a missing converter is a platform bug, not a
   service call.
