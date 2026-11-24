from pathlib import Path
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
sys.path.insert(0, str(OUT / 'support'))
from benchmarks.asr_only import enforce_no_tracker
enforce_no_tracker()
from benchmarks.capture_keen_book import main

extra = sys.argv[1:]
sdk = ROOT / 'output/keen-corpus-21750e9/public/vendor/keenasr'
sys.argv = [sys.argv[0], '--output', str(OUT), '--sdk', str(sdk),
            '--bundle', str(sdk / 'models/keenAK3m-nnet3chain-en-us.tgz'),
            '--browser', 'C:/Program Files/Google/Chrome/Application/chrome.exe', *extra]
main()
