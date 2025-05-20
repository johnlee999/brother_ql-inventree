import sys
from brother_ql.cli import cli
from click.testing import CliRunner

def test_print_copies():
    runner = CliRunner()
    result = runner.invoke(cli, [
        '-m', 'QL-820NWB',
        '-p', 'tcp://192.168.24.72',
        'print',
        '-l', '62x100',
        '--copies', '3',
        '--no-cut',
        'label.png',
    ])
    # result = runner.invoke(cli, [
    #     '-m', 'TD-4550DNWB',
    #     '-p', 'tcp://192.168.24.71',
    #     'print',
    #     '-l', 'td62x100_300dpi',
    #     '--copies', '3',
    #     '--no-cut',
    #     'label.png',
    # ])
    print('exit_code:', result.exit_code)
    print('output:')
    print(result.output)
    
    if result.exception:
      print('exception:', result.exception)
      import traceback
      traceback.print_exception(*result.exc_info)
    assert result.exit_code == 0

if __name__ == '__main__':
    test_print_copies() 
