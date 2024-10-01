# UPS Power Module

UPS Power Module is a system server to display the UPS Power Module's power (and other stats).

## Setup
```
./install.sh <password>
```

## To refresh startup service after modifying *display_server.py*:
```
sudo systemctl stop ups_display.service
sudo python3 setup.py install
sudo systemctl start ups_display.service
```
