param
(
    [string]$cloudbaseinitdir
)

$patch_code = @'
from mock import patch

def custom_setattr(self, attr, value):
    if attr == '_router_ip' and value:
        value = value.split(':')[0]
    return super(self.__class__, self).__setattr__(attr, value)

with patch('cloudbaseinit.metadata.services.cloudstack.'
           'CloudStack.__setattr__', custom_setattr):  
    from cloudbaseinit._shell import main
    main()
'@

mv $cloudbaseinitdir\shell.py $cloudbaseinitdir\_shell.py -ErrorAction ignore
rm $cloudbaseinitdir\shell.pyc -ErrorAction ignore
echo $patch_code | Out-File -Encoding utf8 $cloudbaseinitdir\shell.py
