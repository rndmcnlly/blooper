# /// script
# dependencies = ["numpy"]
# ///
"""Inspect an OOK/PWM remote capture in HackRF .cs8 format (interleaved int8 I,Q).

    uv run --script tools/ook_inspect.py blooper/bloop_f310500000_s4000000.cs8 [--fs 4000000]

Prints: duration, noise floor, the tone's offset from the tuned center
(tune + offset = the remote's real carrier), and the on/off run lengths in
microseconds, which is where the DIP code lives.

Written in 2026 while archiving blooper, to re-derive what the 2022 capture
and resynth files contain.
"""
import argparse

import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("paths", nargs="+")
ap.add_argument("--fs", type=float, default=4_000_000, help="sample rate in Hz")
ap.add_argument("--runs", type=int, default=40, help="how many runs to print")
args = ap.parse_args()

for path in args.paths:
    iq = np.fromfile(path, dtype=np.int8).astype(np.float32).reshape(-1, 2)
    z = iq[:, 0] + 1j * iq[:, 1]
    mag = np.abs(z)
    print(f"\n## {path}")
    print(f"   {len(z)} samples = {len(z) / args.fs * 1e3:.1f} ms; |iq| max {mag.max():.0f}, median {np.median(mag):.1f}")

    # Carrier offset: FFT over only the "on" samples.
    on_raw = mag > mag.max() * 0.4
    zz = z[on_raw][: 2**18]
    spec = np.abs(np.fft.fftshift(np.fft.fft(zz * np.hanning(len(zz)))))
    freqs = np.fft.fftshift(np.fft.fftfreq(len(zz), 1 / args.fs))
    print(f"   tone offset from tuned center: {freqs[spec.argmax()] / 1e3:+.1f} kHz")

    # Envelope: 10 us moving average, then threshold into on/off runs.
    win = max(1, int(args.fs * 10e-6))
    env = np.convolve(mag, np.ones(win) / win, mode="same")
    on = env > env.max() * 0.4
    edges = np.flatnonzero(np.diff(on.astype(np.int8))) + 1
    runs = np.diff(np.concatenate([[0], edges, [len(on)]]))
    state = bool(on[0])
    out = []
    for r in runs:
        out.append(f"{'H' if state else 'L'}{round(r / args.fs * 1e6)}")
        state = not state
    print(f"   {len(out)} runs (state + microseconds):")
    print("   " + " ".join(out[: args.runs]))
