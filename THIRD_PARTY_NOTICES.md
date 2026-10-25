# Third-party notices

The MIT license in LICENSE applies to Local Audio Studio's project code.
Third-party components and downloaded assets retain their original licenses.
This source repository does not include model weights, reference waveforms,
recordings, generated audio, the Python environment or vendored dependencies.

## Chatterbox and watermarking

Setup downloads Chatterbox from https://github.com/resemble-ai/chatterbox at
revision 5de7a54aa4e5e2baadb0182dde554908b48b85c2. The downloaded source retains
its license. The upstream MIT notice is reproduced below for reference.
Perth watermarking remains enabled; its pinned dependency retains its license.

MIT License

Copyright (c) 2025 Resemble AI

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## Models and reference recordings

- Chatterbox weights are downloaded from ResembleAI/chatterbox on Hugging Face
  at revision 5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18. The model card is downloaded
  alongside the weights; local hashes are written to models/manifest.json.
- LibriSpeech reference samples are CC BY 4.0. Credit: Vassil Panayotov,
  Guoguo Chen, Daniel Povey and Sanjeev Khudanpur; LibriVox volunteer readers.
  https://www.openslr.org/12 and https://creativecommons.org/licenses/by/4.0/
  Setup preserves speaker metadata, utterance IDs, source hashes, transcripts,
  transformations and attribution in voices/attribution.json and SPEAKERS.TXT.
- CMU ARCTIC RMS, SLT and CLB voice references are downloaded separately from
  http://festvox.org/cmu_arctic/ and retain the original permissive CMU license.
  Source copyright, permission text, transformations and hashes are retained in
  each generated profile attribution file and included with generated jobs.

Downloaded voice recordings are not relicensed by this project's MIT license.
Other Python packages retain the notices and licenses in their distributions.
