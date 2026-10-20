# Movie Night 20-10 – LoveWorld: edit timeline (draft 1)

Total length **3:08**, 1920×1080. Background song: *Story Of A Warrior* (John Michael Howell).

| Video time | Section | Scene | From | Source time |
|---|---|---|---|---|
| 0:00 | Opening | Jesus calls Mary by name ("Who are you?" … "I have called you by name. You are mine.") | I Have Called You By Name | 2:29.5 – 3:02.4 |
| 0:32 | Montage 1 | Mary hugs Jesus ("Fear not") | I Have Called You By Name | 3:20.3 – 3:26.5 |
| 0:38 | Montage 1 | Peter's nets fill with fish | The Miracle of the Fish | 1:32.8 – 1:49.6 |
| 0:54 | Montage 1 | Peter: "Depart from me, I am a sinful man" | The Miracle of the Fish | 3:09.9 – 3:15.3 |
| 0:59 | Montage 1 | Jesus with the children ("Smart men lack wisdom") | Jesus Loves the Little Children | 0:46.8 – 0:50.3 |
| 1:02 | Montage 1 | Jesus walks on water | Jesus Walks On Water | 2:24.4 – 2:46.7 |
| 1:23 | Montage 2 | Jesus heals the leper ("Be cleansed") | Jesus Heals the Leper | 1:27.1 – 2:03.4 |
| 1:59 | Montage 2 | Jesus preaches to the 5,000 | Jesus Feeds the 5,000 | 0:00 – 0:10 |
| 2:08 | Montage 2 | Jesus prays over the bread | Jesus Feeds the 5,000 | 5:09.8 – 5:38 |
| 2:35 | Montage 2 | The disciples find the baskets full | Jesus Feeds the 5,000 | 7:33.4 – 8:06.1 |
| 3:05 | End | Fade to black | | |

## Transitions
- Fade in from black (1.5 s) at the start, fade out to black (3 s) at the end.
- Soft dissolves between clips (1 s into the montage, 0.5 s inside Montage 1, 0.75 s inside Montage 2).
- Dip to black between Montage 1 and Montage 2.

## Sound
- The song plays under the whole video. It starts at 0:05 and its ending lines up with the final fade.
- The song is 2:10 long, so its chorus section is repeated once to stretch it to fit. The repeat point (about 1:37 in the video) is matched on the beat.
- When someone speaks, the song drops so the line is clear. Between lines, the film's own sound is lowered so the song carries the montage.
- The overall volume is evened out to a standard level (−14 LUFS).

## Not included (not in the Drive folder)
- Jesus cleanses the Temple
- Mary hugging Jesus ("light" version)
- Jesus being taken away (Season 5 finale)

## Rebuilding
Clip times, transitions and sound levels live in `edit/timeline.json`. To re-render, put the source files in a folder and run:

```
python3 edit/build.py --media /path/to/media --out movie_night.mp4
```

The script needs `ffmpeg`. When clips change, re-run `edit/detect_speech.py` (needs `faster-whisper`) to refresh `edit/speech.json`, which tells the build where the dialogue is.
