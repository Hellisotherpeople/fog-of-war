# Fog of War — Kursk battle video

Upload **fog-of-war-kursk-linkedin.mp4** directly using LinkedIn's video upload.
Use **fog-of-war-kursk-cover.jpg** if you want a custom thumbnail. The video has
burned-in captions and works with the sound off; the audio is the game's own
procedural battle effects, mixed from the captured events.

- 28 seconds, 1080 × 1350, 4:5 portrait, 30 fps.
- H.264 High / yuv420p video; stereo AAC, 48 kHz.
- Fast-start MP4, about 15.3 MB.
- Four views of one simulated Kursk battle: contact, armour, barrage, advance.

This is an editorial observer capture from the real game renderer, with the
fog lifted, the player's HUD and injury vignette omitted, and the camera soldier
protected as in the existing GIF recorder. The simulation runs at five game
seconds per video second. There are no staged explosions, stock footage, or
external music. `capture.json` records the seed, camera positions and turn ranges.

Rebuild from the project root (requires ffmpeg):

```sh
.venv/bin/python tools/make_linkedin_video.py
```

Verified the complete file decodes, its 840 frames and 28-second audio track,
the 4:5 aspect ratio and codecs, audio without clipped samples, and that the
MP4 metadata precedes the media data. `contact-sheet.jpg` is the visual review.

LinkedIn supports this file type, resolution, aspect ratio and frame rate:
[video upload requirements](https://www.linkedin.com/help/linkedin/answer/a548372).
Its published [video design recommendations](https://business.linkedin.com/advertise/ads/sponsored-content/video-ads/specs)
also include MP4, 30 fps and 1080 × 1350 portrait video. 4:5 was chosen to give
the battlefield and captions room in a mobile feed.

Autoplay is controlled by each viewer's
[LinkedIn settings](https://www.linkedin.com/help/linkedin/answer/a566341);
a video file cannot override that preference.
