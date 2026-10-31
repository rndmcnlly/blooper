I'm trying to record the signal of the garage door and replay it so I can open the door without the blooper.

According to the FCC registraton, 310MHz is the transmit frequency, and I can confirm this with gqrx.

If you push the button from different angles, the frequency varies: https://twitter.com/rndmcnlly/status/1525321238742069248

I've used GQRX to make a manual recording: gqrx_20220514_040510_310000000_1000000_fc.raw
Similar data decoded to audio: gqrx_20220514_035921_309982200.wav

I'm using `hackrf_transfer` to record and replay in a repeatable way.

So far, the commands look like:

	hackrf_transfer -r last.cs8 -s 4M -f 310500000 -l 16 -a 1
	hackrf_transfer -t last.cs8 -s 4M -f 310500000 -x 32 -a 1 

I need to understand the various gain levels more. I think I should use the main 14dB amp on both steps.

Inspecting the waveform with `inspectrum`, I see OOK with a ~255Hz symbol rate. A burst of 8 symbols matches the DIP switch settings. A burst is followed by an identical length quiet period (8 symbols long).
