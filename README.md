# FreedoWM
<small><i>Pronunciation: /ˈfɹiːdəm/</i></small>

### Installation
There are two scripts helping you to install FreedoWM:
1.  setup.py
    * Installs FreedoWM to your path but doesn't configure the desktop manager to show the option of using FreedoWM
    * Example: `sudo python3.7 setup.py install`
2.  install.sh 
    * Executes `setup.py` and configures your desktop manager (it also adds the freedowm-session executable)
    * Example: `sudo ./install.sh`