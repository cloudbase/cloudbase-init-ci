# Retrieve physical network adapter details in this order:
# mac, address, gateway, netmask, dns, dhcp line by line,
# where each new adapter is separated by a new line.


$nics = Get-WmiObject -ComputerName . Win32_NetworkAdapterConfiguration | `
        Where-Object { $_.IPAddress -ne $null }
foreach ($nic in $nics)
{
    $nic.MACAddress
    $nic.IPAddress
    $nic.DefaultIPGateway
    $nic.IPSubnet
    $nic.DNSServerSearchOrder
    $nic.DHCPEnabled
    ""
}
