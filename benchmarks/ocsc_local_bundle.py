"""Package already-downloaded OCSC inputs for transfer between your own PCs.

No downloads, uploads or credentials. The ZIP contains restricted local data
and must stay out of Git and web hosting without contributor permission.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = 'output/ocsc/portable_inventory.json'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def portable(value):
    if isinstance(value, dict):
        return {k:portable(v) for k,v in value.items()}
    if isinstance(value, list):
        return [portable(v) for v in value]
    return value.replace('\\','/') if isinstance(value,str) else value


def export_bundle(target):
    target = target.resolve()
    if not target.is_relative_to(ROOT/'output'):
        raise ValueError('Export inside ignored output/; copy the ZIP to your own other PC afterward.')
    if target.exists():
        raise FileExistsError(f'Refusing to overwrite {target}; choose a new name.')
    files=[]
    for sid in ('6008','7057'):
        files += [ROOT/f'recordings/{sid}_reading.{ext}' for ext in ('wav','txt','srt')]
        files += [ROOT/f'recordings/{sid}_full.{ext}' for ext in ('wav','txt','srt','cha')]
        files += sorted((ROOT/f'recordings/transcripts/{sid}_reading').glob('*.srt'))
    files += [ROOT/f'output/ocsc/{n}.json' for n in ('subset','subset-early')]
    files += sorted((ROOT/'output/ocsc/manifests').glob('*.json'))
    for path in ('output/timely-hints-jobs.json',
                 'output/ocsc/source/reading-races-thesis.pdf','recordings/INDEX.md'):
        if (ROOT/path).is_file():files.append(ROOT/path)
    if not all(p.is_file() for p in files):
        raise FileNotFoundError('Some OCSC inputs are missing. See recordings/OCSC_LOCAL_SETUP.md.')
    target.parent.mkdir(parents=True,exist_ok=True)
    inventory={}
    with zipfile.ZipFile(target,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=4) as archive:
        for path in files:
            name=path.relative_to(ROOT).as_posix();data=path.read_bytes()
            if path.name in ('subset.json','subset-early.json','timely-hints-jobs.json'):
                data=json.dumps(portable(json.loads(data)),indent=2).encode('utf-8')
            archive.writestr(name,data)
            inventory[name]={'sha256':digest(data),'bytes':len(data)}
        archive.writestr(INVENTORY,json.dumps(dict(files=inventory,
            notice='OCSC local evaluation data. For personal-PC transfer, not web redistribution. '
                   'Follow https://talkbank.org/0share/rules.html'),indent=2))
    print(f'Created {target.relative_to(ROOT)} ({target.stat().st_size/1024**2:.1f} MiB; {len(inventory)} files).')


def read_verified(source):
    with zipfile.ZipFile(source) as archive:
        inventory=json.loads(archive.read(INVENTORY))['files']
        names=archive.namelist()
        if len(names)!=len({n.casefold() for n in names}) or set(names)!=set(inventory)|{INVENTORY}:
            raise ValueError('Unexpected or duplicate ZIP members.')
        if sum(i.file_size for i in archive.infolist()) > 1024**3:
            raise ValueError('Bundle exceeds the 1 GiB local-subset budget.')
        for name,expected in inventory.items():
            path=PurePosixPath(name)
            if '\\' in name or path.is_absolute() or '..' in path.parts:
                raise ValueError('Unsafe archive path.')
            allowed = (name in {'recordings/INDEX.md','output/ocsc/subset.json',
                'output/ocsc/subset-early.json','output/timely-hints-jobs.json',
                'output/ocsc/source/reading-races-thesis.pdf'} or
                re.fullmatch(r'recordings/(6008|7057)_(reading|full)\.(wav|txt|srt|cha)',name) or
                re.fullmatch(r'recordings/transcripts/(6008|7057)_reading/[A-Za-z0-9._-]+\.srt',name) or
                re.fullmatch(r'output/ocsc/manifests/[A-Za-z0-9_-]+\.json',name))
            if not allowed:raise ValueError(f'Not an OCSC data path: {name}')
            destination=(ROOT/name).resolve()
            if not destination.is_relative_to(ROOT):raise ValueError('Path outside checkout.')
            data=archive.read(name)
            if len(data)!=expected['bytes'] or digest(data)!=expected['sha256']:
                raise ValueError(f'Integrity failure: {name}')
        return inventory


def import_bundle(source):
    inventory=read_verified(source)
    # Check all conflicts before writing. Existing identical files are safe.
    for name,expected in inventory.items():
        path=ROOT/name
        if path.exists() and digest(path.read_bytes())!=expected['sha256']:
            raise FileExistsError(f'Existing file differs: {name}; preserve or rename it before importing.')
    with zipfile.ZipFile(source) as archive:
        for name in list(inventory)+[INVENTORY]:
            destination=(ROOT/name).resolve()
            if not destination.is_relative_to(ROOT):raise ValueError('Path outside checkout.')
            destination.parent.mkdir(parents=True,exist_ok=True)
            if not destination.exists():destination.write_bytes(archive.read(name))
    print(f'Imported/verified {len(inventory)} files into this checkout. No network upload performed.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    export=commands.add_parser('export');export.add_argument('--output',type=Path,required=True)
    for mode in ('verify','import'):
        command=commands.add_parser(mode);command.add_argument('--archive',type=Path,required=True)
    args=parser.parse_args()
    if args.command=='export':export_bundle(args.output)
    elif args.command=='verify':print(f'Verified {len(read_verified(args.archive))} bundled files.')
    else:import_bundle(args.archive)


if __name__=='__main__':main()
