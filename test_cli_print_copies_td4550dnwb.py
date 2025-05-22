import sys
import os
from brother_ql.cli import cli
from click.testing import CliRunner

def test_print_copies_file():
    runner = CliRunner()
    result = runner.invoke(cli, [
        '-m', 'TD-4550DNWB',
        '-p', 'tcp://192.168.24.71',
        'print',
        '-l', 'td62x100_300dpi',
        '--copies', '2',
        '--no-cut',
        'label.png',
    ])
    print('exit_code:', result.exit_code)
    print('output:')
    print(result.output)
    if result.exception:
        print('exception:', result.exception)
        import traceback
        traceback.print_exception(*result.exc_info)
    assert result.exit_code == 0

def test_print_copies_stdin():
    runner = CliRunner()
    # label.pngをバイナリで読み込んで標準入力として渡す
    with open('label.png', 'rb') as f:
        img_data = f.read()
    result = runner.invoke(cli, [
        '-m', 'TD-4550DNWB',
        '-p', 'tcp://192.168.24.71',
        'print',
        '-l', 'td62x100_300dpi',
        '--copies', '2',
        '--no-cut',
        '-',
    ], input=img_data)
    print('exit_code (stdin):', result.exit_code)
    print('output (stdin):')
    print(result.output)
    if result.exception:
        print('exception (stdin):', result.exception)
        import traceback
        traceback.print_exception(*result.exc_info)
    # debug_stdin.pngの有無と内容確認
    if os.path.exists('debug_stdin.png'):
        print('debug_stdin.png exists')
        import hashlib
        with open('debug_stdin.png', 'rb') as f:
            debug_md5 = hashlib.md5(f.read()).hexdigest()
        with open('label.png', 'rb') as f:
            label_md5 = hashlib.md5(f.read()).hexdigest()
        print('debug_stdin.png md5:', debug_md5)
        print('label.png md5:', label_md5)
        assert debug_md5 == label_md5
    else:
        print('debug_stdin.png does not exist')
    assert result.exit_code == 0

if __name__ == '__main__':
    # test_print_copies_file()
    test_print_copies_stdin() 
