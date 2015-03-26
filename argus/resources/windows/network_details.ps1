# Retrieve physical network adapter details in this order:
# mac, address, gateway, netmask, dns, dhcp line by line,
# where each new adapter is separated by a new line.


$nics = Get-WmiObject -ComputerName . Win32_NetworkAdapterConfiguration | `
        Where-Object { $_.IPAddress -ne $null }
$sep = "----"

foreach ($nic in $nics)
{
    # On some cases, the join is used only to
    # normalize NULs to empty strings.
    $details = @(
        $sep,
        ($nic.MACAddress -join " "),
        ($nic.IPAddress -join " "),
        ($nic.DefaultIPGateway -join " "),
        ($nic.IPSubnet -join " "),
        ($nic.DNSServerSearchOrder -join " "),
        ($nic.DHCPEnabled -join " ")
    )
    foreach ($detail in $details)
    {
        echo $detail
    }
}
