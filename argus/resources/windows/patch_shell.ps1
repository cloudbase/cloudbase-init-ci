param
(
    [string]$cloudbaseinitdir
)

$patch_code = @'
import os
from cloudbaseinit.original_shell import main

def create_file(path):
    with open(path, 'w') as stream:
        pass

def heart_beat():
    first = "C:\\cloudbaseinit_unattended"
    second = "C:\\cloudbaseinit_normal"

    if not os.path.exists(first):
        create_file(first)
    else:
        create_file(second)

heart_beat()
if __name__ == '__main__':
    main()
'@

mv $cloudbaseinitdir\shell.py $cloudbaseinitdir\original_shell.py -ErrorAction SilentlyContinue
rm $cloudbaseinitdir\shell.pyc -ErrorAction SilentlyContinue
echo $patch_code | Out-File -Encoding utf8 $cloudbaseinitdir\shell.py
