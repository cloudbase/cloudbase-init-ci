param
(
    [string]$cloudbaseinitdir
)

$patch_code = @'
from mock import patch


def custom_getattribute(self, attr):
    value = object.__getattribute__(self, attr)
    if attr == '_router_ip' and value:
        return value.split(':')[0]
    return value

def main():
    with patch('cloudbaseinit.metadata.services.cloudstack.'
               'CloudStack.__getattribute__', custom_getattribute):  
        from cloudbaseinit._shell import main as orig_main
        orig_main()

if __name__ == '__main__':
    main()
'@

mv $cloudbaseinitdir\shell.py $cloudbaseinitdir\_shell.py -ErrorAction ignore
rm $cloudbaseinitdir\shell.pyc -ErrorAction ignore
echo $patch_code | Out-File -Encoding utf8 $cloudbaseinitdir\shell.py
