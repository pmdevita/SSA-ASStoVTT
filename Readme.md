# SSA/ASS to WebVTT

Converts SSA/ASS format subtitles to VTT and attempts to retain as much detail as possible. 

WebVTT is a useful format for adding subtitles or captions to HTML5 video. Unfortunately, no browser currently 
implements the full specification. This converter makes use of what is currently available for VTT subtitles.

## Usage

`python3 ssatovtt.py subtitles.ass subtitles.vtt`

I'd also recommend styling the subs by throwing something like this in your CSS

```
video::cue {
	color: white;
	background-color: transparent;
	text-shadow:
		-1px -1px 0 #000,
		1px -1px 0 #000,
		-1px 1px 0 #000,
		1px 1px 0 #000;
}
```