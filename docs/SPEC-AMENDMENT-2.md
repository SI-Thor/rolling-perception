# Spec Amendment 2 — presence: any device is a terminal, the system sits at the table

*2026-11-01, Casey's framing, recorded while Slice 1 was building.*

Amendment 1 made thin devices first-class IO. Casey extends it:

> The system should be device agnostic. You should be able to pull
> up a browser on the ProArt laptop and use the speaker and
> microphone connected directly on the network to the Thor — and
> the system can be present with you, like it's there at the table.

## What this means in the architecture

1. **A terminal lends senses, not just a screen.** Any browser on
   the LAN can offer the platform its camera, microphone, speaker
   and display as a bundle. The Thor remains the only mind:
   perception, memory and voice are computed there; the device is
   IO. Joining is opening a page — no install, no app, no pairing
   ritual beyond being on the house network.
2. **Presence is a session, not a sensor.** A presence session is
   something a person deliberately opens (like joining a call) and
   can see is live. Voice is conversational: the system listens,
   answers through the same device's speaker, and its attention is
   the rolling perception already in the substrate — the room's
   streams, the change feed, the ledger — so "what did I miss?"
   and "what's happening at the dock?" are questions it can answer
   from its own records.
3. **Prior art is inventoried, not rebuilt.** The fleet already
   proved this loop on this hardware: Radio Room (ProArt + Thor,
   2026-10-23) — hold-to-talk capture, faster-whisper STT on the
   Thor side, a persona brain, Piper TTS dressed as radio audio,
   per-stage receipts. Confluence generalises that point solution
   into a platform capability any terminal can join, and inherits
   its lessons (subprocess audio IO, not PortAudio; placement is a
   wash, contention decides).

## The boundary that does NOT move

Panel 1's refusal stands: **no always-on ambient microphone
perception.** Presence audio exists only inside a session a person
opened, with a live indicator, and ends when the session ends.
The distinction is consent and visibility: a voice at the table
you invited, versus a microphone that never sleeps. Camera change
perception (Slice 1) is a separate, declared watch; presence does
not silently widen it.

## Sequencing

Slice 1 (live change feed + shelf + install pack) is unchanged and
already building. Presence becomes the headline of the next slice
after Slice 1's acceptance, reusing the Radio Room pipeline as its
starting point and the ledger/health surfaces from Slice 1 as its
face. Its acceptance will include a from-the-chair test: a
conversation held through a laptop browser, at the table, with the
system answering from the live ledger.

## Lineage (one paragraph, deliberately no more)

Confluence is the quilt paradigm wearing product clothes: anything
is a cell in a graph — a stream, a terminal, a model, a camera, a
voice — and the connections between cells are second-class citizens
next to the function each cell achieves with whatever power and IO
is attached to it. The substrate's rings are one rendering of
cell-to-cell flow; the ledger is the graph written as text. The
build stays on Confluence; the paradigm is the inheritance, not a
second project.
