__version__ = '0.1.0'

from fastapi import FastAPI, Response, status
from fastapi.responses import RedirectResponse

import os

import asyncio

app = FastAPI()

@app.get("/")
def root():
        return RedirectResponse("/docs")

@app.get("/health")
async def health(response: Response):
    """Check if this service is ready to broadcast (a compatible SDR is available)."""
    proc = await asyncio.create_subprocess_shell(
            "hackrf_info",
            stdout=asyncio.subprocess.PIPE)
    hackrf_info_output, _ = await proc.communicate()
    ok = b"Found HackRF" in hackrf_info_output
    if not ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": ("pass" if ok else "fail"),
        "description": "a hacky garage door blooper",
        "notes": hackrf_info_output,
    }

@app.post("/bloop")
async def bloop():
    """Broadcast the garage door opener signal."""
    waveform_filename = os.path.join(os.path.dirname(__file__), "resynth_f310500000_s4000000.cs8")
    proc = await asyncio.create_subprocess_shell(
            f"hackrf_transfer -t {waveform_filename} -s 4M -f 310500000 -x 34 -a 1",
            stdout=asyncio.subprocess.PIPE)
    hackrf_transfer_output, _ = await proc.communicate()
    return hackrf_transfer_output
