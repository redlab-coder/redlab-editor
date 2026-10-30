"""Reuse only complete Windows artifacts built by this repository on main.

The source commit must match exactly. PR artifacts and partial/failed runs never
qualify. A missing or expired artifact falls back to a new full Windows build.
No installer is executed here.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import zipfile

from publish import PRODUCTS, REPOSITORY, gh, validate_artifacts

ROOT = Path(__file__).resolve().parents[1]


def source_sha():
    return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()


def workflow(product):
    return '.github/workflows/'+PRODUCTS[product][2].removesuffix('-v')+'.yml'


def artifact_name(product, run_id):
    return PRODUCTS[product][0]+'-Windows-'+str(run_id)


def trusted_run(run, product, commit, *, current_run=None):
    expected_path = workflow(product)
    return (run.get('head_sha') == commit and run.get('event') in ('push', 'workflow_dispatch')
            and run.get('path') == expected_path
            and run.get('repository', {}).get('full_name') == REPOSITORY
            and run.get('head_repository', {}).get('full_name') == REPOSITORY
            and ((run.get('head_branch') == 'main' and run.get('conclusion') == 'success')
                 or (current_run is not None and str(run.get('id')) == str(current_run))))


def record(product, directory):
    """Called only after every required Windows test has succeeded."""
    if os.environ.get('GITHUB_ACTIONS') != 'true' or os.environ.get('RUNNER_OS') != 'Windows':
        raise ValueError('Registre a aprovação apenas no runner Windows descartável.')
    namespace = {}
    exec((ROOT/'apps'/product/'version.py').read_text(encoding='utf-8'), namespace)
    manifest, checks = validate_artifacts(product, PRODUCTS[product][2]+namespace['VERSION'], directory)
    names = set(checks)|{'SHA256SUMS.txt'}
    evidence = dict(schema=1, product=product, source_sha=source_sha(),
                    version=manifest['version'], run_id=int(os.environ['GITHUB_RUN_ID']),
                    run_attempt=int(os.environ['GITHUB_RUN_ATTEMPT']), full_validation=True,
                    sha256={name: hashlib.sha256((directory/name).read_bytes()).hexdigest() for name in sorted(names)})
    (directory/'build.json').write_text(json.dumps(evidence, indent=2)+'\n', encoding='utf-8')


def verify_files(product, directory, commit, run_id, attempt):
    evidence = json.loads((directory/'build.json').read_text(encoding='utf-8'))
    if (evidence.get('schema') != 1 or evidence.get('product') != product
            or evidence.get('source_sha') != commit or evidence.get('run_id') != run_id
            or evidence.get('run_attempt') != attempt or evidence.get('full_validation') is not True):
        raise ValueError('O comprovante não corresponde à compilação aprovada.')
    namespace = {}
    exec((ROOT/'apps'/product/'version.py').read_text(encoding='utf-8'), namespace)
    if evidence.get('version') != namespace['VERSION']:
        raise ValueError('A versão compilada difere do código selecionado.')
    _, checks = validate_artifacts(product, PRODUCTS[product][2]+namespace['VERSION'], directory)
    names = set(checks)|{'SHA256SUMS.txt'}
    if set(evidence.get('sha256', {})) != names:
        raise ValueError('Comprovante de integridade incompleto.')
    for name in names:
        if hashlib.sha256((directory/name).read_bytes()).hexdigest() != evidence['sha256'][name]:
            raise ValueError('Arquivo alterado após aprovação: '+name)


def restore(product, run_id, destination):
    commit = source_sha()
    run = json.loads(gh('api', f'repos/{REPOSITORY}/actions/runs/{run_id}'))
    namespace = {}
    exec((ROOT/'apps'/product/'version.py').read_text(encoding='utf-8'), namespace)
    expected_ref = 'refs/tags/'+PRODUCTS[product][2]+namespace['VERSION']
    current = (os.environ.get('GITHUB_RUN_ID') if os.environ.get('GITHUB_ACTIONS') == 'true'
               and os.environ.get('GITHUB_REF') == expected_ref else None)
    if not trusted_run(run, product, commit, current_run=current):
        raise ValueError('A compilação precisa pertencer ao código exato e a um workflow confiável.')
    artifacts = json.loads(gh('api', f'repos/{REPOSITORY}/actions/runs/{run_id}/artifacts'))['artifacts']
    matches = [item for item in artifacts if item['name'] == artifact_name(product, run_id) and not item['expired']]
    if len(matches) != 1:
        raise ValueError('Artefato aprovado ausente ou expirado.')
    artifact = matches[0]
    if artifact.get('workflow_run', {}).get('head_sha') != commit:
        raise ValueError('A origem do artefato não corresponde ao commit.')
    data = subprocess.check_output(['gh', 'api', f'repos/{REPOSITORY}/actions/artifacts/{artifact["id"]}/zip'])
    if artifact.get('digest') != 'sha256:'+hashlib.sha256(data).hexdigest():
        raise ValueError('O arquivo recebido difere do artefato registrado no GitHub.')
    with tempfile.TemporaryDirectory(prefix='redlab-approved-') as temporary:
        staging = Path(temporary)
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = archive.namelist()
            executable = PRODUCTS[product][0]
            namespace = {}
            exec((ROOT/'apps'/product/'version.py').read_text(encoding='utf-8'), namespace)
            expected = {f'{executable}-Setup-{namespace["VERSION"]}.exe', executable+'-Portable.exe',
                        'update.json', 'SHA256SUMS.txt', 'build.json'}
            if len(names) != len(expected) or set(names) != expected or sum(item.file_size for item in archive.infolist()) > 1024**3:
                raise ValueError('Conteúdo inesperado no artefato de compilação.')
            archive.extractall(staging)
        evidence = json.loads((staging/'build.json').read_text(encoding='utf-8'))
        attempt = evidence.get('run_attempt')
        if type(attempt) is not int or not 1 <= attempt <= run['run_attempt']:
            raise ValueError('Tentativa de compilação inválida.')
        # A publisher-only retry may follow a Windows success in an earlier
        # attempt. Verify that exact attempt instead of needlessly rebuilding.
        jobs = json.loads(gh('api', f'repos/{REPOSITORY}/actions/runs/{run_id}/attempts/{attempt}/jobs'))['jobs']
        if not any(job['name'] == 'windows / validate' and job['conclusion'] == 'success' for job in jobs):
            raise ValueError('A validação completa do Windows não foi aprovada nessa tentativa.')
        verify_files(product, staging, commit, int(run_id), attempt)
        destination.mkdir(parents=True, exist_ok=True)
        if any(destination.iterdir()):
            raise ValueError('Use uma pasta de destino vazia para receber o artefato.')
        for path in staging.iterdir():
            (destination/path.name).write_bytes(path.read_bytes())
    return artifact


def find(product, wait_seconds=600):
    """Wait for an already-running main build; never wait for a nonexistent run."""
    commit = source_sha()
    deadline = time.monotonic()+wait_seconds
    while True:
        response = json.loads(gh('api', f'repos/{REPOSITORY}/actions/workflows/{Path(workflow(product)).name}/runs?head_sha={commit}&per_page=100'))
        # A manual reuse check runs on main too; it cannot wait for itself.
        candidates = [run for run in response['workflow_runs']
                      if str(run['id']) != os.environ.get('GITHUB_RUN_ID')]
        for run in candidates:
            if trusted_run(run, product, commit):
                artifacts = json.loads(gh('api', f'repos/{REPOSITORY}/actions/runs/{run["id"]}/artifacts'))['artifacts']
                if any(item['name'] == artifact_name(product, run['id']) and not item['expired'] for item in artifacts):
                    return run['id']
        pending = any(run.get('head_branch') == 'main' and run['status'] in ('queued', 'in_progress', 'waiting', 'pending') for run in candidates)
        if not pending or time.monotonic() >= deadline:
            return None
        time.sleep(min(10, max(0, deadline-time.monotonic())))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('find', 'record', 'restore'))
    parser.add_argument('product', choices=PRODUCTS)
    parser.add_argument('--run-id', type=int)
    parser.add_argument('--directory', type=Path)
    args = parser.parse_args()
    directory = args.directory or ROOT/'apps'/args.product/'dist'
    if args.action == 'record':
        record(args.product, directory)
    elif args.action == 'restore':
        if args.run_id is None:
            parser.error('--run-id é obrigatório para restore')
        restore(args.product, args.run_id, directory)
    else:
        selected = find(args.product)
        if selected:
            # Validate the download before deciding to omit the Windows fallback.
            try:
                with tempfile.TemporaryDirectory() as temporary:
                    restore(args.product, selected, Path(temporary)/'approved')
            except (ValueError, KeyError, zipfile.BadZipFile) as error:
                print('Artefato não reutilizado: '+str(error))
                selected = None
        with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as output:
            output.write(f'reused={str(selected is not None).lower()}\nrun_id={selected or ""}\n')
        print('Compilação aprovada reutilizável: '+str(selected) if selected else 'Será executada uma nova validação completa no Windows.')


if __name__ == '__main__':
    main()
