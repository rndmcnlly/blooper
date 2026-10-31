# blooper

A virtual garage door remote: a web endpoint that makes a HackRF One transmit a resynthesized copy of a remote's signal. It replaced a Linear 1-button remote ([FCC ID EF4DNT00002](https://fccid.io/EF4DNT00002)) and ran on a Raspberry Pi 1 Model B (armv6l, 512 MB) from 2022 until the door was replaced. Nearly all of it, from the Pi's systemd units to the signal processing notebook, was done from a phone: ssh for the Pi, a phone browser for Jupyter.

This repo is an archive, kept as a quick reference for future SDR projects. The code, notebook and lab notes are from 2022 and untouched. This README was written in 2026 by agents working with me, reconstructing the project from what it left behind on two machines (see [How this archive was made](#how-this-archive-was-made-2026)).

## The story (May 2022)

1. **Find the signal** (May 13): the FCC filing said 310 MHz, and gqrx confirmed it. It also showed the frequency **moving depending on how the remote was held** ([tweet](https://twitter.com/rndmcnlly/status/1525321238742069248)). Cheap remotes use a loose oscillator, and a hand nearby detunes it. The two gqrx recordings in `research/` are from that night.
2. **Look at it** with inspectrum: on-off keying, bursts of 8 symbols (one per DIP switch), each burst followed by an equally long silence. The first estimate of the symbol rate (about 255 Hz) was wrong; the notebook later got 646 Hz.
3. **Record and replay repeatably** (May 22) with `hackrf_transfer`, captured at `-s 4M -f 310500000 -l 16 -a 1` (`research/raw_bloop_...cs8`, 0.43 s). Raw replay worked, but it rebroadcasts the capture's noise along with the signal.
4. **Resynthesize** (May 26–27) in `research/Resynthesis.ipynb`: crop the capture down to `blooper/bloop_...cs8`, find the carrier, recover the symbol clock, then build a clean signal from scratch and save `blooper/resynth_...cs8`. The notebook ends with: "I was able to use this resynthesized signal to open the garage door!"
5. **Make it a service** (from May 22, revised through Dec 2022): FastAPI on a Unix socket, nginx, and an mDNS name, so any phone on the home wifi could open the door at `http://blooper.local`.

## Architecture

```
phone on home wifi
  -> http://blooper.local          mDNS name, published as a CNAME by avahi
  -> nginx :80                     deploy/nginx-blooper.local
  -> unix:~/blooper/blooper.sock   uvicorn, run by deploy/blooper.service
  -> FastAPI app                   blooper/__init__.py (the whole app, ~40 lines)
       GET  /        -> redirect to /docs (Swagger UI is the "button")
       GET  /health  -> 200 if `hackrf_info` finds a HackRF, else 503
       POST /bloop   -> hackrf_transfer -t resynth_f310500000_s4000000.cs8 \
                          -s 4M -f 310500000 -x 34 -a 1
  -> HackRF One on USB
```

Design choices worth reusing:

- **Unix socket behind nginx**, not a TCP port: nginx owns port 80 and the name, and the app needs no privileges.
- **mDNS CNAME** via [`mdns-publisher`](https://github.com/carlosefr/mdns-publisher) (`pip install mdns-publisher`, gives `mdns-publish-cname`): one host can answer to several `.local` names, one per service. This only works on the LAN; mDNS does not cross a tailnet.
- **Health check as a hardware probe**: `/health` shells out to `hackrf_info` and looks for `Found HackRF`. Cheap, and it catches the usual failure (the USB device dropped off).
- **No DSP at runtime.** The Pi 1 only replays a file. All the signal work happened ahead of time, on a laptop.

## The signal

All `.cs8` files are HackRF format: interleaved signed 8-bit I,Q, here at 4 MS/s tuned to 310.5 MHz (file names record `f` and `s`). The gqrx `.raw` file is complex float32 at 1 MS/s tuned to 310.0 MHz. `uv run --script tools/ook_inspect.py blooper/*.cs8` reproduces the numbers below, which were measured independently in 2026 and agree with the 2022 notebook.

| | `bloop_...cs8` (cropped capture) | `resynth_...cs8` (synthesized) |
|---|---|---|
| length | 212 ms | 207 ms |
| noise floor (median abs IQ) | 3.6 | 0.0 |
| peak amplitude | 81 | 64 |
| tone offset from 310.5 MHz | -1.40 MHz | -1.40 MHz |
| `1` symbol (on/off) | ~770 / ~775 us, jittery | 783 / 766 us |
| `0` symbol (on/off) | ~192 / ~1354 us, jittery | 202 / 1346 us |
| silence after each burst | ~13.72 ms | 13.73 ms |

What that means:

- **Modulation**: on-off keying with pulse-width encoding. The symbol clock is 645.8 Hz (1.55 ms per symbol). A `1` is on for half the symbol, a `0` for an eighth. A burst is 8 symbols, followed by 8 symbols of silence, repeated about 8.5 times per press.
- **The code**: `pattern = array([1,1,1,1,0,0,0,0])`, straight from the notebook. It is a **fixed code**, not a rolling code, so a replay works forever.
- **The real carrier moves.** In this capture it is about 309.1 MHz (310.5 - 1.40), while the gqrx recording was named for 309.98 MHz. The receiver is wide enough not to care. The notebook found it as an FFT peak at +2.60 MHz and read it as a wrapped negative frequency, which is how a spectrum from complex samples behaves above Nyquist. Tuning the HackRF above the signal also keeps it clear of the HackRF's DC spike at the center frequency.
- **How the resynth was built**: an ideal on/off envelope from the pattern and the recovered clock, smoothed with a short Gaussian (edges shaped to keep the transmission narrow), multiplying a clean complex tone at the measured offset, at amplitude 0.5 (64 in int8). The notebook then adds ±0.5 LSB of dither before `astype('int8')`. Because that cast truncates toward zero, the dither never survives on silent samples, which is why the noise floor is exactly 0.0. Harmless, but worth knowing next time: round, don't truncate.
- **TX settings**: `-x 34` is the TX VGA gain (0–47 dB), `-a 1` turns on the RF amp (about +14 dB). Replay started at `-x 32`. Start lower on new hardware.

### Lessons for the next SDR project

1. Find the signal in a waterfall first (gqrx) and expect a cheap transmitter to wander.
2. Look before you code (inspectrum): count symbols and bursts by eye, then let FFTs refine the numbers. The eyeballed symbol rate here was off by more than 2x.
3. Capture with the tuner deliberately off-center, and read the offset from the capture instead of trusting the label.
4. Transmit a clean synthesized waveform rather than replaying a noisy capture. The envelope's spectrum gives you the symbol clock.
5. Keep the always-on box dumb: replaying a file is all a Pi 1 needs to do.

### About publishing the capture

These files are a working key for any Linear 310 MHz fixed-code receiver whose DIP switches are set to `11110000`. They are published anyway: the door is gone, the code is about as guessable as a code can be, and fixed-code openers like this can be brute-forced or replayed by anyone with a cheap radio. That weakness is the point of this repo, not a secret it reveals. Transmitting is your responsibility; use your own equipment, and stay inside the rules for unlicensed devices where you are.

## Files

| path | what |
|---|---|
| `blooper/__init__.py` | the FastAPI app |
| `blooper/bloop_...cs8`, `blooper/resynth_...cs8` | cropped capture and the waveform actually transmitted |
| `deploy/` | the two systemd units and the nginx site, as they were on the Pi |
| `research/2022-lab-notes.md` | lab notes from May 13–22, 2022, verbatim |
| `research/Resynthesis.ipynb` | the resynthesis notebook, outputs and plots included |
| `research/raw_bloop_...cs8` | the uncropped HackRF capture (0.43 s) |
| `research/gqrx_..._fc.raw`, `research/gqrx_....wav` | first-night gqrx recordings: raw IQ, and audio demodulated at 309.98 MHz |
| `tools/ook_inspect.py` | added in 2026: prints carrier offset and pulse timings for any `.cs8` |

## Running it

Requires the `hackrf` tools (`hackrf_info`, `hackrf_transfer`) and Poetry.

```
poetry install
poetry run uvicorn blooper:app --uds blooper.sock
```

Then install `deploy/`: the two systemd units into `/etc/systemd/system/`, and the nginx site into `/etc/nginx/sites-available/`, symlinked from `sites-enabled/`. Paths assume user `adam` and the repo at `~/blooper`.

The notebook uses 2022-era `%pylab inline` and expects `bloop_f310500000_s4000000.cs8` in its working directory; copy it next to the notebook to re-run it.

## How this archive was made (2026)

There was no git repository, and the Pi held only the service: no notebook, no numpy, and a bash history that had long since evicted anything from 2022 (it was mostly systemd wrangling, plus `perf_5.10 record -p 315`, where 315 MHz briefly became a process ID). So an agent worked it out forensically:

1. Over ssh, it read the Pi's app, units, nginx site, the 2022 `README.rst`, and a hardware dump identifying the HackRF.
2. It decoded both `.cs8` files blind with what became `tools/ook_inspect.py`: the `LLLLSSSS` pulse pattern, the -1.40 MHz offset, and the fact that the resynth was synthetic rather than a cleaned recording.
3. Asked where the signal work happened, I remembered Jupyter in a phone browser. Nothing on the Pi, so a Spotlight search on my current laptop for the string `310500000` turned up the 2022 lab folder, with the notebook, lab notes, and every intermediate capture. The work had actually happened on the previous MacBook: Migration Assistant carried the folder over in December 2023 with its May 2022 creation dates intact, and the notebook was re-saved once on the new machine in March 2024 (hence Python 3.12 in its metadata).
4. The notebook confirmed the blind decode (pattern, offset, symbol clock) and corrected a few guesses, which is how this README ended up citing the notebook rather than paraphrasing a reconstruction.

## Original 2022 README

Verbatim from the Pi's `README.rst` (which was Markdown all along).

> # blooper
>
> A virtual garage door blooper!
>
> Replaces device with [FCC ID EF4DNT00002](https://fccid.io/EF4DNT00002) using a [FastAPI](https://fastapi.tiangolo.com/) based interface to drive a [HackRF One](https://greatscottgadgets.com/hackrf/one/). The specific configuration of DIP switches is baked into a pre-recorded signal.
>
> ## Usage
>
>     $ poetry run uvicorn blooper:app --uds blooper.sock
>
> ## Related glue
>
> See also local files:
>  - `/etc/systemd/system/mdns-publish-blooper-cname.service`: make blooper.local resolve to this machine
>  - `/etc/systemd/system/blooper.service`: run the above command to provide service on blooper.sock
>  - `/etc/nginx/sites-enabled/blooper.local`: serve http for blooper.local via proxy to blooper.sock
>
> ## Future todo:
> - a nicer web interface so you don't need to bloop via swagger
> - simplify systemd stuff (maybe blooper becomes a named socket thingy?)

## License

MIT, see `LICENSE`.
