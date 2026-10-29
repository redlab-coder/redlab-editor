"""Publish the tested suite. This never writes an application's update feed."""
import argparse
import json
from pathlib import Path
from bundle import BUNDLE, digest, validate_bundle
from publish import REPOSITORY, gh


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tag')
    parser.add_argument('--directory', type=Path, default=BUNDLE/'dist')
    args = parser.parse_args()
    contents, checks = validate_bundle(args.directory, args.tag)
    # Resolve every child to a published stable release before exposing the suite.
    for item in contents['products']:
        tag = item['url'].split('/download/')[1].split('/')[0]
        release = json.loads(gh('api', f'repos/{REPOSITORY}/releases/tags/{tag}'))
        asset = next(asset for asset in release['assets'] if asset['name'] == item['installer'])
        if (release['draft'] or release['prerelease'] or asset['state'] != 'uploaded'
                or asset['digest'] != 'sha256:'+item['sha256'] or asset['size'] != item['size']):
            raise ValueError('O pacote deve conter os instaladores públicos aprovados.')
    gh('release', 'create', args.tag, '--repo', REPOSITORY, '--verify-tag', '--draft',
       '--title', 'RedLab Editor · Pacote completo '+contents['version'],
       '--notes-file', str(BUNDLE/'RELEASE_NOTES.md'))
    gh('release', 'upload', args.tag, '--repo', REPOSITORY,
       *(str(args.directory/name) for name in (*checks, 'SHA256SUMS.txt')))
    release = json.loads(gh('release', 'view', args.tag, '--repo', REPOSITORY, '--json', 'assets'))
    if {asset['name'] for asset in release['assets']} != set(checks)|{'SHA256SUMS.txt'}:
        raise ValueError('Publicação incompleta.')
    for asset in release['assets']:
        if asset['state'] != 'uploaded' or asset['digest'] != 'sha256:'+digest(args.directory/asset['name']):
            raise ValueError('O arquivo publicado difere do pacote testado.')
    gh('release', 'edit', args.tag, '--repo', REPOSITORY, '--draft=false', '--latest')
    print('Pacote completo publicado. Os três canais individuais foram preservados.')


if __name__ == '__main__':
    main()
