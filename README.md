# OctoPrint-MGSetup
This plugin provides general setup and configuration interfaces for control of the MakerGear M3 Single and Independent Dual Extruder printers.

## Setup

We strongly recommend only using full Release versions of this plugin, as those have been fully tested and release for general use.



To install the absolute latest, currently testing version:

Install via the bundled [Plugin Manager](https://github.com/foosel/OctoPrint/wiki/Plugin:-Plugin-Manager)
or manually using this URL:

    https://github.com/MakerGear/MakerGear_OctoPrint_Setup/archive/master.zip

## Development

Setup:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -e .
pip install -r requirements/dev.txt
```

Setup in docker for development:
```bash
# start octoprint in one terminal
docker-compose up

# in the other install the plugin in dev mode
docker exec -it makergear_octoprint_setup_octoprint_1 bash
octoprint dev plugin:install
cd /MakerGear_OctoPrint_Setup/
python setup.py develop
```

Code formatting:

```bash
black .
```
