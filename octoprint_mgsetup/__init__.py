# coding=utf-8

from .mgsetup_plugin import MGSetupPlugin

__plugin_implementation__ = MGSetupPlugin()
__plugin_hooks__ = {
    "octoprint.comm.protocol.gcode.received": __plugin_implementation__.process_z_offset,
    "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information,
    "octoprint.server.http.routes": __plugin_implementation__.route_hook,
}
__plugin_pythoncompat__ = ">=2.7,<4"
