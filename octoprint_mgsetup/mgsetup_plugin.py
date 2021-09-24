# coding=utf-8

from logging.handlers import RotatingFileHandler
from logging.handlers import TimedRotatingFileHandler
from octoprint import __version__
from octoprint.events import Events
from zipfile import *
import datetime
import errno
import flask
import hashlib
import logging
import octoprint.plugin
import octoprint.settings
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import traceback
import urllib.request, urllib.error, urllib.parse
import yaml


class MGSetupPlugin(
    octoprint.plugin.StartupPlugin,
    octoprint.plugin.TemplatePlugin,
    octoprint.plugin.SettingsPlugin,
    octoprint.plugin.AssetPlugin,
    octoprint.plugin.SimpleApiPlugin,
    octoprint.plugin.EventHandlerPlugin,
):
    def __init__(self):
        self.old_z_offset = 0
        self.first_tab = True
        self.first_run_complete = False
        self.hide_debug = False
        self.first_tab_name = "plugin_mgsetup"
        self.newhost = socket.gethostname()
        self.serial = -1
        self.registered = False
        self.activated = False
        self.act_api_key = 0
        self.act_server = "http://whatever.what"
        self.next_reminder = -1
        self.internet_connection = False
        self.tooloffsetline = ""
        self.zoffsetline = ""
        self.plugin_version = ""
        self.ip = ""
        self.firmwareline = ""
        self.localfirmwareline = ""
        self.probeline = ""
        self.probe_offset_line = ""
        self.print_active = False
        self.mg_logger = logging.getLogger("mgLumberJack")
        self.mg_logger.setLevel(logging.DEBUG)
        self.mg_logger_first_run = logging.getLogger("mgFirstRun")
        self.mg_logger_first_run.setLevel(5)
        self.mg_logger_permanent = logging.getLogger("mgPermanent")
        self.mg_logger_permanent.setLevel(5)
        self.mg_logger.info("right after init test!?")
        self.printer_value_version = 0
        self.printer_value_good = False
        self.current_project_name = ""
        self.current_project_print_success_time = 0
        self.current_project_print_fail_time = 0
        self.current_project_machine_fail_time = 0
        self.total_print_success_time = 0
        self.total_print_fail_time = 0
        self.total_machine_fail_time = 0
        self.current_project_print_success_time_friendly = ""
        self.current_project_print_fail_time_friendly = ""
        self.current_project_machine_fail_time_friendly = ""
        self.total_print_success_time_friendly = ""
        self.total_print_fail_time_friendly = ""
        self.total_machine_fail_time_friendly = ""
        # TODO - this is ugly, should probably combine all of these into a dict, but...works for now.
        self.printing = False
        self.current_print_start_time = 0
        self.current_print_elapsed_time = 0
        self.print_elapsed_timer = octoprint.util.RepeatedTimer(
            12, self.update_elapsed_time
        )
        self.update_elapsed_timer = False
        self.smbpatchstring = ""

    def create_loggers(self):
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler = logging.handlers.TimedRotatingFileHandler(
            self._basefolder + "/logs/mgsetup.log", when="d", interval=3, backupCount=10
        )
        first_run_handler = logging.handlers.RotatingFileHandler(
            self._basefolder + "/logs/mgsetupFirstRun.log",
            maxBytes=100000000,
            backupCount=20,
        )
        # first_run_handler.setLevel(5)
        permanent_handler = logging.handlers.RotatingFileHandler(
            self._basefolder + "/logs/mgsetupPermanent.log",
            maxBytes=100000000,
            backupCount=20,
        )
        # permanent_handler.setLevel(5)
        handler.setFormatter(formatter)
        first_run_handler.setFormatter(formatter)
        permanent_handler.setFormatter(formatter)
        self.mg_logger.addHandler(handler)
        # self.mg_logger.addHandler(first_run_handler)
        # self.mg_logger.addHandler(permanent_handler)
        self.mg_logger_permanent.addHandler(permanent_handler)
        self.mg_logger_first_run.addHandler(first_run_handler)

        # self.mg_logger.info("on_after_startup mgLogger test!")
        self.mg_log("general test", 0)
        # self.mgLog("permanent test",2)
        # self.mgLog("firstrun test",3)
        # self.mgLog("permanent and first run test",4)

    def mg_log(self, message, level=2):
        self._logger.info(message)
        self.mg_logger.info(message)
        if level == 2:
            self.mg_logger_permanent.info(message)
            self.mg_logger.info("Also logged to PERMANENT")
        if level == 3:
            self.mg_logger_first_run.info(message)
            self.mg_logger.info("Also logged to FIRST RUN")
        if level == 4:
            self.mg_logger_permanent.info(message)
            self.mg_logger_first_run.info(message)
            self.mg_logger.info("Also logged to PERMANENT and FIRST RUN")

            # Defined as an API target as well, so we can target it from octoprint client - [wherever]/octoprint client post_json '/api/plugin/mgsetup' '{"command":"mg_log","stringToLog":"[whateverYouWantToLog]","priority":"[priorityLevel]"}

    def on_settings_initialized(self):
        self.mg_logger.info("First mgLogger test!?")
        self._logger.info("MGSetup on_settings_initialized triggered.")
        # octoprint.settings.Settings.add_overlay(octoprint.settings.settings(), dict(controls=dict(children=dict(name="Medium Quality"), dict(commands=["M201 X900 Y900", "M205 X20 Y20", "M220 S50"]))))
        # octoprint.settings.Settings.set(octoprint.settings.settings(), ["controls", "children", "name"],["Fan Orn"])
        # octoprint.settings.Settings.add_overlay(octoprint.settings.settings(), ["controls"],["name"]
        # dict(api=dict(enabled=False),
        #                                  server=dict(host="127.0.0.1",
        #                                             port=5001))

        octoprint.settings.Settings.get(
            octoprint.settings.settings(), ["appearance", "components", "order", "tab"]
        )
        self.first_tab = self._settings.get(["firstTab"])
        if self.first_tab:
            self.first_tab_name = "plugin_mgsetup"
            # octoprint.settings.Settings.set(octoprint.settings.settings(),["appearance", "components", "order", "tab"],["plugin_mgsetup", "temperature", "control", "gcodeviewer", "terminal", "timelapse"],force=True)
            octoprint.settings.Settings.add_overlay(
                octoprint.settings.settings(),
                dict(
                    appearance=dict(
                        components=dict(
                            order=dict(
                                tab=[
                                    "plugin_mgsetup",
                                    "temperature",
                                    "control",
                                    "gcodeviewer",
                                    "terminal",
                                    "timelapse",
                                ]
                            )
                        )
                    )
                ),
            )
        else:
            self.first_tab_name = "temperature"
            # octoprint.settings.Settings.set(octoprint.settings.settings(),["appearance", "components", "order", "tab"],["temperature", "control", "gcodeviewer", "terminal", "plugin_mgsetup", "timelapse"],force=True)
            octoprint.settings.Settings.add_overlay(
                octoprint.settings.settings(),
                dict(
                    appearance=dict(
                        components=dict(
                            order=dict(
                                tab=[
                                    "temperature",
                                    "control",
                                    "gcodeviewer",
                                    "terminal",
                                    "plugin_mgsetup",
                                    "timelapse",
                                ]
                            )
                        )
                    )
                ),
            )
        self.first_run_complete = self._settings.get(["firstRunComplete"])
        self.hide_debug = self._settings.get(["hideDebug"])
        if self._settings.get(["serialNumber"]) != -1:
            self.serial = self._settings.get(["serialNumber"])
            self._logger.info("Retrieved serialNumber from Settings.")
        else:
            if os.path.isfile("/boot/serial.txt"):
                with open("/boot/serial.txt", "r") as f:
                    self.serial = f.readline().strip()
                    self._settings.set(["serialNumber"], self.serial)
                    self._settings.save()
            else:
                self._logger.info("serial.txt does not exist!")
        self._logger.info(self.serial)
        self.registered = self._settings.get(["registered"])
        self.activated = self._settings.get(["activated"])
        self.next_reminder = self._settings.get(["nextReminder"])
        self.plugin_version = self._settings.get(["pluginVersion"])
        self.current_project_print_success_time = self._settings.get(
            ["currentProjectPrintSuccessTime"]
        )
        self.current_project_name = self._settings.get(["currentProjectName"])
        self.total_print_success_time = self._settings.get(["totalPrintSuccessTime"])
        self.current_project_print_fail_time = self._settings.get(
            ["currentProjectPrintFailTime"]
        )
        self.current_project_machine_fail_time = self._settings.get(
            ["currentProjectMachineFailTime"]
        )
        self.total_print_fail_time = self._settings.get(["totalPrintFailTime"])
        self.total_machine_fail_time = self._settings.get(["totalMachineFailTime"])

        # 		octoprint.settings.Settings.set(dict(appearance=dict(components=dict(order=dict(tab=[MGSetupPlugin().first_tab_name, "temperature", "control", "gcodeviewer", "terminal", "timelapse"])))))
        # 		octoprint.settings.Settings.set(dict(appearance=dict(name=["MakerGear "+self.newhost])))
        # __plugin_settings_overlay__ = dict(appearance=dict(components=dict(order=dict(tab=[MGSetupPlugin().first_tab_name]))))
        if self._settings.get(["prefixDisplayName"]):
            octoprint.settings.Settings.set(
                octoprint.settings.settings(),
                ["appearance", "name"],
                ["MakerGear " + self.newhost],
            )
        else:
            octoprint.settings.Settings.set(
                octoprint.settings.settings(), ["appearance", "name"], [self.newhost]
            )
        self.active_profile = octoprint.settings.Settings.get(
            octoprint.settings.settings(), ["printerProfiles", "default"]
        )
        self._logger.info(self.active_profile)
        self._logger.info(
            "extruders: "
            + str(
                (
                    self._printer_profile_manager.get_all()[self.active_profile][
                        "extruder"
                    ]["count"]
                )
            )
        )
        self._logger.info(
            self._printer_profile_manager.get_current_or_default()["extruder"]["count"]
        )
        self._logger.info("Hello")

    def check_internet(self, timeout, iterations, url):
        self._logger.info("MGSetup checkInternet triggered.")
        if url == "none":
            url = "http://google.com"
        elif url == "fail":
            url = "http://httpstat.us/404"
        else:
            url = url
        for i in range(0, iterations + 1):
            self._logger.info(
                "Testing Internet Connection, iteration "
                + str(i)
                + " of "
                + str(iterations)
                + ", timeout of "
                + str(timeout)
                + " ."
            )
            try:
                response = urllib.request.urlopen(url, timeout=timeout)
                self._logger.info("Check Internet Passed.  URL: " + str(url))
                self.internet_connection = True
                self._plugin_manager.send_plugin_message(
                    "mgsetup", dict(internetConnection=self.internet_connection)
                )
                return True
            except urllib.error.URLError as err:
                pass
            if i >= iterations:
                self._logger.info(
                    "Testing Internet Connection Failed, iteration "
                    + str(i)
                    + " of "
                    + str(iterations)
                    + ", timeout of "
                    + str(timeout)
                    + " .  Looking for URL: "
                    + str(url)
                )
                self.internet_connection = False
                self._plugin_manager.send_plugin_message(
                    "mgsetup", dict(internetConnection=self.internet_connection)
                )
                return False

    def on_after_startup(self):
        self.create_loggers()
        self._logger.info("MGSetup on_after_startup triggered.")
        # self._logger.info("extruders: "+str(self._printer_profile_manager.get_current()))
        # self._logger.info("extruders: "+str(self._settings.get(["printerProfiles","currentProfileData","extruder.count"])))
        self.current_position = "empty for now"
        self._logger.info(self.newhost)
        self.check_internet(3, 3, "none")
        # self._logger.info(self._printer_profile_manager.get_all())
        # self._logger.info(self._printer_profile_manager.get_current())
        self._logger.info(
            self._printer_profile_manager.get_all()["_default"]["extruder"]["count"]
        )
        # self._logger.info(__version__)

        try:  # a bunch of code with minor error checking and user alert...ion to copy scripts to the right location; should only ever need to be run once
            os.makedirs(self.script_path("gcode"))
        except OSError:
            if not os.path.isdir(self.script_path("gcode")):
                raise

        self.copy_maintenance_files("gcode", "scripts/gcode")
        self.copy_maintenance_files("cura", "slicingProfiles/cura")
        self.copy_maintenance_files("scripts", "scripts")

        # set file permissions
        scripts_dir = self._settings.getBaseFolder("scripts")
        for file in os.listdir(scripts_dir):
            if ".sh" in file:
                os.chmod(os.path.join(scripts_dir, file), 0o755)

        try:
            os.chmod(self._basefolder + "/static/js/hostname.js", 0o666)
        except OSError:
            self._logger.info("Hostname.js doesn't exist?")
        except:
            raise
        try:
            os.chmod(self._basefolder + "/static/patch/patch.sh", 0o755)
        except OSError:
            self._logger.info("Patch.sh doesn't exist?")
        except:
            raise
        try:
            os.chmod(self._basefolder + "/static/patch/logpatch.sh", 0o755)
        except OSError:
            self._logger.info("logpatch.sh doesn't exist?")
        except:
            raise

        subprocess.call(
            self.script_path("hosts.sh")
        )  # recreate hostsname.js for external devices/ print finder

        try:
            self.ip = str(
                (
                    [
                        l
                        for l in (
                            [
                                ip
                                for ip in socket.gethostbyname_ex(socket.gethostname())[
                                    2
                                ]
                                if not ip.startswith("127.")
                            ][:1],
                            [
                                [
                                    (
                                        s.connect(("8.8.8.8", 53)),
                                        s.getsockname()[0],
                                        s.close(),
                                    )
                                    for s in [
                                        socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                                    ]
                                ][0][1]
                            ],
                        )
                        if l
                    ][0][0]
                )
            )
        except IOError as e:
            self._logger.info(e)
        except:
            raise
        self.get_local_firmware_version()
        self.admin_action(dict(action="sshState"))
        if self._settings.get(["printing"]):
            self.mg_log(
                "It looks like the machine crashed while printing - updating machineFail times and reseting.",
                2,
            )
            self.current_project_machine_fail_time = (
                self.current_project_machine_fail_time
                + (self.current_print_elapsed_time - self.current_print_start_time)
            )
            self.total_machine_fail_time = self.total_machine_fail_time + (
                self.current_print_elapsed_time - self.current_print_start_time
            )
            self.printing = False
            self.current_print_start_time = 0
            self.current_print_elapsed_time = 0
            self._settings.set(
                ["currentProjectMachineFailTime"],
                self.current_project_machine_fail_time,
            )
            self._settings.set(
                ["currentProjectMachineFailTimeFriendly"],
                str(
                    datetime.timedelta(
                        seconds=int(self.current_project_machine_fail_time)
                    )
                ),
            )

            self._settings.set(["totalMachineFailTime"], self.total_machine_fail_time)
            self._settings.set(
                ["totalMachineFailTimeFriendly"],
                str(datetime.timedelta(seconds=int(self.total_machine_fail_time))),
            )

            self._settings.set(["printing"], self.printing)
            self._settings.set(["currentPrintStartTime"], self.current_print_start_time)
            self._settings.set(
                ["currentPrintElapsedTime"], self.current_print_elapsed_time
            )
            self._settings.save()
            self.print_elapsed_timer.start()

        # if
        try:
            smb_hash_val = hashlib.md5(
                open("/etc/samba/smb.conf").read()
            ).hexdigest()  # != "03dc1620b398cbe3d2d82e83c20c1905":
            if smb_hash_val == "44c057b0ffc7ab0f88c1923bdd32b559":
                self.smbpatchstring = "Patch Already In Place"
                self.mg_log("smb.conf hash matches patched file, no need to patch", 2)
            elif smb_hash_val == "95b44915e267400669b2724e0cce5967":
                self.smbpatchstring = "Patch was required: smb.conf has been patched"
                self.mg_log(
                    "smb.conf hash matches unpatched file, now patching file", 2
                )
                # self.mg_log("smb.conf actual hash: "+str(smb_hash_val))
                self.patch_smb()

            else:
                self.smbpatchstring = (
                    "Custom smb.conf file present: patch status unknown"
                )
                self.mg_log(
                    "Custom smb.conf file present: patch status unknown. No Action", 2
                )
        except Exception as e:
            self._logger.info(str(e))

    def get_template_configs(self):
        self._logger.info("MGSetup get_template_configs triggered.")
        return [
            dict(type="navbar", custom_bindings=True),
            dict(type="settings", custom_bindings=True),
            dict(type="tab", template="mgsetup_tab.jinja2", div="tab_plugin_mgsetup"),
            # dict(type="tab", template="mgsetup_maintenance_tab.jinja2", div="tab_plugin_mgsetup_maintenance", name="MakerGear Maintenance"),
            dict(
                type="tab",
                template="mgsetup_maintenance_tab-cleanup.jinja2",
                div="tab_plugin_mgsetup_maintenance-cleanup",
                name="MakerGear Maintenance",
            ),
        ]

    def get_settings_defaults(self):
        self._logger.info("MGSetup get_settings_defaults triggered.")
        return dict(
            hideDebug=True,
            firstRunComplete=False,
            registered=False,
            activated=False,
            firstTab=True,
            serialNumber=-1,
            nextReminder=-1,
            pluginVersion="master",
            localFirmwareVersion="",
            sshOn=False,
            warnSsh=True,
            currentProjectName="",
            currentProjectPrintSuccessTime=0,
            currentProjectPrintFailTime=0,
            currentProjectMachineFailTime=0,
            totalPrintSuccessTime=0,
            totalPrintFailTime=0,
            totalMachineFailTime=0,
            currentProjectPrintSuccessTimeFriendly="",
            currentProjectPrintFailTimeFriendly="",
            currentProjectMachineFailTimeFriendly="",
            totalPrintSuccessTimeFriendly="",
            totalPrintFailTimeFriendly="",
            totalMachineFailTimeFriendly="",
            printing=False,
            currentPrintStartTime=0,
            currentPrintElapsedTime=0,
            prefixDisplayName=True,
        )

    def get_settings_restricted_paths(self):
        self._logger.info("MGSetup get_settings_restricted_paths triggered.")
        return dict(
            user=[
                ["serialNumber", "registered", "activated"],
            ]
        )

    def get_assets(self):
        self._logger.info("MGSetup get_assets triggered.")
        return dict(
            js=["js/mgsetup.js", "js/mgsetup_maintenance.js"],
            css=["css/mgsetup.css", "css/overrides.css"],
            img=["img/*"],
            gcode=["gcode/*"],
            videojs=["video-js/*"],
        )

    def remind_later(self):
        self._logger.info("MGSetup remindLater triggered.")
        self.next_reminder = time.mktime(time.gmtime()) + 604800
        self._logger.info(
            "Next Reminder: "
            + str(self.next_reminder)
            + ", currently: "
            + str(time.mktime(time.gmtime()))
        )
        self._settings.set(["nextReminder"], self.next_reminder)
        self._settings.save()

    def on_event(self, event, payload):
        self._logger.info("MGSetup on_event triggered.")
        if event == Events.POSITION_UPDATE:
            self._logger.info(payload)
            self.current_position = dict(payload)
            self.position_state = "fresh"
            ##			self._logger.info(current_position)
            return

        if event == Events.CLIENT_OPENED:
            # self._logger.info(payload + " connected")
            # self.serial = ""
            self.send_current_values()
            self._logger.info(self._printer_profile_manager.get_current_or_default())
            # self._plugin_manager.send_plugin_message("mgsetup", dict(zoffsetline = self.zoffsetline))
            # self._plugin_manager.send_plugin_message("mgsetup", dict(tooloffsetline = self.tooloffsetline))
            self._plugin_manager.send_plugin_message("mgsetup", dict(ip=self.ip))
            self._plugin_manager.send_plugin_message(
                "mgsetup", dict(octoprintVersion=__version__)
            )
            self._plugin_manager.send_plugin_message(
                "mgsetup", dict(mgsetupVersion=self._plugin_version)
            )
            self._plugin_manager.send_plugin_message(
                "mgsetup", dict(smbpatchstring=self.smbpatchstring)
            )

            # self._plugin_manager.send_plugin_message("mgsetup", dict(firmwareline = self.firmwareline))
            # self._plugin_manager.send_plugin_message("mgsetup", dict(probeOffsetLine = self.probe_offset_line))
            self._logger.info(str(self.next_reminder))
            # if (self.internet_connection == False ):
            self.check_internet(3, 5, "none")
            # else:
            # 	self._plugin_manager.send_plugin_message("mgsetup", dict(internetConnection = self.internet_connection))

            if (self.activated == False) or (self.registered == False):
                if (self.next_reminder <= time.mktime(time.gmtime())) and (
                    self.next_reminder > 0
                ):
                    self._logger.info("nextReminder is in the past and not 0")
                    self._plugin_manager.send_plugin_message(
                        "mgsetup", dict(pleaseRemind=True)
                    )
                else:
                    self._logger.info("nextReminder in the future or 0")
                    self._logger.info(str(self.next_reminder))
                    self._logger.info(str(time.mktime(time.gmtime())))
                return

        if event == Events.PRINT_STARTED:
            self.print_active = True
            self.printing = True
            self.current_print_start_time = time.mktime(time.gmtime())
            self.current_print_elapsed_time = self.current_print_start_time
            self._settings.set(["printing"], self.printing)
            self._settings.set(["currentPrintStartTime"], self.current_print_start_time)
            self._settings.set(
                ["currentPrintElapsedTime"], self.current_print_elapsed_time
            )
            self._settings.save()
            self._logger.info("Current print start time:")
            self._logger.info(self.current_print_start_time)
            self.update_elapsed_timer = True

        if (
            (event == Events.PRINT_FAILED)
            or (event == Events.PRINT_CANCELLED)
            or (event == Events.PRINT_DONE)
            or (event == Events.CONNECTED)
            or (event == Events.DISCONNECTED)
        ):
            self.print_active = False

        if (event == Events.PRINT_FAILED) or (event == Events.PRINT_CANCELLED):
            self.printing = False
            current_time = time.mktime(time.gmtime())
            if (self.current_print_start_time != 0) and (
                current_time > self.current_print_start_time
            ):
                self.current_project_print_fail_time = (
                    self.current_project_print_fail_time
                    + (current_time - self.current_print_start_time)
                )
                self._settings.set(
                    ["currentProjectPrintFailTime"],
                    self.current_project_print_fail_time,
                )
                self._settings.set(
                    ["currentProjectPrintFailTimeFriendly"],
                    str(
                        datetime.timedelta(
                            seconds=int(self.current_project_print_fail_time)
                        )
                    ),
                )

                self.total_print_fail_time = self.total_print_fail_time + (
                    current_time - self.current_print_start_time
                )
                self._settings.set(["totalPrintFailTime"], self.total_print_fail_time)
                self._settings.set(
                    ["totalPrintFailTimeFriendly"],
                    str(datetime.timedelta(seconds=int(self.total_print_fail_time))),
                )

                self._logger.info("totalPrintFailTime:")
                self._logger.info(self.total_print_fail_time)
            self.current_print_start_time = 0
            self._settings.set(["currentPrintStartTime"], self.current_print_start_time)
            self.update_elapsed_timer = False
            self.current_print_elapsed_time = 0
            self._settings.set(
                ["currentPrintElapsedTime"], self.current_print_elapsed_time
            )
            self._settings.save()
            self.trigger_settings_update()

            # self.current_project_print_success_time = self.current_project_print_success_time +

        if event == Events.PRINT_DONE:
            self._logger.info("PRINT_DONE triggered.")
            self.current_project_print_success_time = (
                self.current_project_print_success_time + payload["time"]
            )
            self.total_print_success_time = (
                self.total_print_success_time + payload["time"]
            )
            self._settings.set(["totalPrintSuccessTime"], self.total_print_success_time)
            self._settings.set(
                ["totalPrintSuccessTimeFriendly"],
                str(datetime.timedelta(seconds=int(self.total_print_success_time))),
            )
            self._settings.set(
                ["currentProjectPrintSuccessTime"],
                self.current_project_print_success_time,
            )
            self._settings.set(
                ["currentProjectPrintSuccessTimeFriendly"],
                str(
                    datetime.timedelta(
                        seconds=int(self.current_project_print_success_time)
                    )
                ),
            )

            self._settings.save()
            # octoprint.settings.Settings.save()
            self.printing = False
            self.current_print_start_time = 0
            self.update_elapsed_timer = False
            self.current_print_elapsed_time = 0
            self._settings.set(["printing"], self.printing)
            self._settings.set(["currentPrintStartTime"], self.current_print_start_time)
            self._settings.set(
                ["currentPrintElapsedTime"], self.current_print_elapsed_time
            )
            self._settings.save()
            self.trigger_settings_update()

        if event == Events.DISCONNECTED:
            self.printer_value_good = False

        if event == Events.CONNECTED:
            self.request_values()

    def trigger_settings_update(self):
        payload = dict(
            config_hash=self._settings.config_hash,
            effective_hash=self._settings.effective_hash,
        )
        self._event_bus.fire(Events.SETTINGS_UPDATED, payload=payload)

    def update_elapsed_time(self):
        if self.printing and self.update_elapsed_timer:
            self.current_print_elapsed_time = time.mktime(time.gmtime())
            self._settings.set(
                ["currentPrintElapsedTime"], self.current_print_elapsed_time
            )
            self._settings.save()
            self._logger.info("New currentPrintElapsedTime:")
            self._logger.info(self.current_print_elapsed_time)

    def _to_unicode(self, s_or_u, encoding="utf-8", errors="strict"):
        """Make sure ``s_or_u`` is a unicode string."""
        if isinstance(s_or_u, str):
            return s_or_u.decode(encoding, errors=errors)
        else:
            return s_or_u

    def _execute(self, command, **kwargs):
        import sarge

        if isinstance(command, (list, tuple)):
            joined_command = " ".join(command)
        else:
            joined_command = command
        # _log_call(joined_command)

        # kwargs.update(dict(async=True, stdout=sarge.Capture(), stderr=sarge.Capture()))

        try:
            p = sarge.run(
                command, async_=True, stdout=sarge.Capture(), stderr=sarge.Capture()
            )
            while len(p.commands) == 0:
                # somewhat ugly... we can't use wait_events because
                # the events might not be all set if an exception
                # by sarge is triggered within the async process
                # thread
                time.sleep(0.01)

            # by now we should have a command, let's wait for its
            # process to have been prepared
            p.commands[0].process_ready.wait()

            if not p.commands[0].process:
                # the process might have been set to None in case of any exception
                # print("Error while trying to run command {}".format(joined_command), file=sys.stderr)
                self._plugin_manager.send_plugin_message(
                    "mgsetup",
                    dict(commandError="Error while trying to run command - 1."),
                )
                self._plugin_manager.send_plugin_message(
                    "mgsetup", dict(commandError=p.stderr.readlines(timeout=0.5))
                )
                self._plugin_manager.send_plugin_message(
                    "mgsetup", dict(commandResponse=p.stdout.readlines(timeout=0.5))
                )
                return None, [], []
        except:
            # print("Error while trying to run command {}".format(joined_command), file=sys.stderr)
            self._plugin_manager.send_plugin_message(
                "mgsetup", dict(commandError="Error while trying to run command - 2.")
            )
            self._plugin_manager.send_plugin_message(
                "mgsetup", dict(commandError=p.stderr.readlines(timeout=0.5))
            )
            self._plugin_manager.send_plugin_message(
                "mgsetup", dict(commandError=traceback.format_exc())
            )
            self._plugin_manager.send_plugin_message(
                "mgsetup", dict(commandResponse=p.stdout.readlines(timeout=0.5))
            )
            # traceback.print_exc(file=sys.stderr)
            return None, [], []

        all_stdout = []
        all_stderr = []
        last_print = None
        try:
            while p.commands[0].poll() is None:
                error_flag = None
                lines = p.stderr.readlines(timeout=0.5)
                if lines:
                    if error_flag == False:
                        self._plugin_manager.send_plugin_message(
                            "mgsetup", dict(commandResponse="\n\r")
                        )

                    lines = [self._to_unicode(x, errors="replace") for x in lines]
                    # _log_stderr(*lines)
                    all_stderr += list(lines)
                    self._plugin_manager.send_plugin_message(
                        "mgsetup", dict(commandError=all_stderr)
                    )
                    all_stderr = []
                    # self.mg_log(lines,2)
                    error_flag = True
                    last_print = True

                lines = p.stdout.readlines(timeout=0.5)
                if lines:
                    lines = [self._to_unicode(x, errors="replace") for x in lines]
                    # _log_stdout(*lines)
                    all_stdout += list(lines)
                    self._logger.info(lines)
                    self._logger.info(all_stdout)
                    self._plugin_manager.send_plugin_message(
                        "mgsetup", dict(commandResponse=all_stdout)
                    )
                    all_stdout = []
                    last_print = True
                    # self.mg_log(lines,2)
                else:
                    # if (error_flag == None) and (last_print == False):
                    # self._plugin_manager.send_plugin_message("mgsetup", dict(commandResponse = "."))
                    last_print = False

        finally:
            p.close()

        lines = p.stderr.readlines()
        if lines:
            lines = [self._to_unicode(x, errors="replace") for x in lines]
            # _log_stderr(*lines)
            all_stderr += lines
            self._plugin_manager.send_plugin_message(
                "mgsetup", dict(commandError=all_stderr)
            )
            all_stderr = []
            self._logger.info(lines)
            # self.mg_log(lines,2)

        lines = p.stdout.readlines()
        if lines:
            lines = [self._to_unicode(x, errors="replace") for x in lines]
            # _log_stdout(*lines)
            all_stdout += lines

            self._logger.info(all_stdout)
            self._logger.info(all_stderr)
            self._plugin_manager.send_plugin_message(
                "mgsetup", dict(commandResponse=all_stdout)
            )
            all_stdout = []
        return p.returncode, all_stdout, all_stderr

    def counter_test(self, action_maybe):
        self._execute(self.script_path("counter.sh"))
        # p = subprocess.call(self.script_path("counter.sh"), shell=True)
        # while p.poll():
        # 	self._logger.info(p.readline())

    def back_up_config_yaml(self):
        config_file = self._settings._configfile
        backup_file = self._settings._configfile + ".backup"

        try:
            if not os.path.isfile(backup_file):
                shutil.copyfile(
                    config_file,
                    backup_file,
                )
                self._plugin_manager.send_plugin_message(
                    "mgsetup",
                    dict(commandResponse="Copied config.yaml to config.yaml.backup.\n"),
                )
            else:
                new_backup = str(datetime.datetime.now().strftime("%y-%m-%d.%H:%M"))
                shutil.copyfile(
                    backup_file,
                    backup_file + "." + new_backup,
                )
                shutil.copyfile(
                    config_file,
                    backup_file,
                )
                self._plugin_manager.send_plugin_message(
                    "mgsetup",
                    dict(
                        commandResponse="Copied config.yaml.backup to config.yaml.backup."
                        + new_backup
                        + " and copied config.yaml to config.yaml.backup.\n"
                    ),
                )
        except IOError as e:
            self._logger.info("Tried to backup config.yaml but encountered an error!")
            self._logger.info("Error: " + str(e))
            self._plugin_manager.send_plugin_message(
                "mgsetup",
                dict(
                    commandError="Tried to backup config.yaml but encountered an error!  Error: "
                    + str(e)
                    + "\n"
                ),
            )
            if not os.path.isfile(backup_file):
                raise
            else:
                self._execute("sudo chgrp pi " + backup_file)
                self._execute("sudo chown pi " + backup_file)
                os.chmod(backup_file, 0o600)
                self._plugin_manager.send_plugin_message(
                    "mgsetup",
                    dict(
                        commandError="Changed the owner, group and permissions of config.yaml.backup - please try to Update Firmware again to backup config.yaml.\n"
                    ),
                )

    def collect_logs(self):
        # src_files = os.listdir(self._basefolder+"/static/maintenance/cura/")
        # main_log_folder = octoprint.settings.Settings.get(octoprint.settings.settings(),["settings", "folder", "logs"])
        main_log_folder = "/home/pi/.octoprint/logs"
        main_logs = os.listdir(main_log_folder)
        plugin_log_folder = self._basefolder + "/logs"
        plugin_logs = os.listdir(plugin_log_folder)

        # for file_name in main_logs:
        # 	allLogs = os.path.join(main_log_folder, file_name)
        # for file_name in plugin_logs:
        # 	allLogs = allLogs + os.path.join(plugin_log_folder, file_name)

        # self._logger.info(allLogs)
        # zipname = "/home/pi/" + str(datetime.datetime.now().strftime('%y-%m-%d.%H.%M'))+".zip"
        try:
            self._plugin_manager.send_plugin_message(
                "mgsetup", dict(commandError="Preparing Logs, Please Wait.\n\n")
            )
            last_five = "".join(list(self.serial)[3:])
            zip_name_date = (
                "MGSetup-Logs-"
                + last_five
                + "-"
                + str(datetime.datetime.now().strftime("%y-%m-%d_%H-%M"))
            )
            zipname = self._basefolder + "/static/maintenance/" + zip_name_date + ".zip"
            with ZipFile(zipname, "w", ZIP_DEFLATED) as logzip:
                # for file_name in allLogs:
                # 	logzip.write(file_name)

                for file_name in main_logs:
                    tempfile = os.path.join(main_log_folder, file_name)
                    logzip.write(tempfile, os.path.basename(tempfile))
                for file_name in plugin_logs:
                    tempfile = os.path.join(plugin_log_folder, file_name)
                    logzip.write(tempfile, os.path.basename(tempfile))

            self._plugin_manager.send_plugin_message(
                "mgsetup",
                dict(commandError="Downloading File: " + str(zip_name_date) + ".zip"),
            )
            self._plugin_manager.send_plugin_message(
                "mgsetup", dict(logFile=zip_name_date + ".zip")
            )
        except Exception as e:
            self._logger.info("collectLogs failed, exception: " + str(e))
            self._plugin_manager.send_plugin_message(
                "mgsetup",
                dict(
                    commandError="There was an exception while trying to collect logs: "
                    + str(e)
                ),
            )

    def get_local_firmware_version(self):
        self._logger.info("local firmware reports itself as: ")
        if os.path.isfile("/home/pi/m3firmware/src/Marlin/Version.h"):
            with open("/home/pi/m3firmware/src/Marlin/Version.h", "r") as f:
                self.filelines = f.readlines()
                self._logger.info(self.filelines[37])
                pattern = r'".+"'
                matchedline = re.search(pattern, self.filelines[37]).group()
                self._logger.info(matchedline)
                self._settings.set(["localFirmwareVersion"], matchedline)
                self._settings.save()
                self.localfirmwareline = matchedline
                self._plugin_manager.send_plugin_message(
                    "mgsetup", dict(localfirmwareline=self.localfirmwareline)
                )

    def update_local_firmware(self):

        # To create a fresh copy of the target folder, git clone -b 1.1.6 https://github.com/MakerGear/m3firmware.git src1.1.6
        self._logger.info("Update Firmware started.")
        self.back_up_config_yaml()
        if not os.path.isfile("/home/pi/m3firmware/src/Marlin/lockFirmware"):
            # self._logger.info(self._execute("git -C /home/pi/m3firmware/src pull"))
            self._execute(
                "git -C /home/pi/m3firmware/src fetch --all; git -C /home/pi/m3firmware/src reset --hard; git -C /home/pi/m3firmware/src pull"
            )

            if os.path.isfile(
                "/home/pi/m3firmware/src/Marlin/Configuration_makergear.h.m3ID"
            ):

                self._logger.info(
                    self._printer_profile_manager.get_current_or_default()["extruder"][
                        "count"
                    ]
                )
                self.active_profile = octoprint.settings.Settings.get(
                    octoprint.settings.settings(), ["printerProfiles", "default"]
                )
                if self.active_profile == None:
                    self.extruder_count = (
                        self._printer_profile_manager.get_current_or_default()[
                            "extruder"
                        ]["count"]
                    )
                else:
                    self._logger.info("Profile: " + self.active_profile)
                    self._logger.info(
                        "extruders: "
                        + str(
                            (
                                self._printer_profile_manager.get_all()[
                                    self.active_profile
                                ]["extruder"]["count"]
                            )
                        )
                    )
                    self.extruder_count = self._printer_profile_manager.get_all()[
                        self.active_profile
                    ]["extruder"]["count"]

                # self._logger.info("extruders: "+str( ( self._printer_profile_manager.get_all() [ self.active_profile ]["extruder"]["count"] ) ) )
                # self.extruder_count = ( self._printer_profile_manager.get_all() [ self.active_profile ]["extruder"]["count"] )

                # self._printer_profile_manager.get_all().get_current()["extruder"]["counter"]
                # self._logger.info("extruders: "+str(self._printer_profile_manager.get_all().get_current()["extruder"]["counter"]))
                if self.extruder_count == 2:
                    try:
                        shutil.copyfile(
                            "/home/pi/m3firmware/src/Marlin/Configuration_makergear.h.m3ID",
                            "/home/pi/m3firmware/src/Marlin/Configuration_makergear.h",
                        )
                        self._logger.info(
                            "Copied the Dual configuration to Configuration_makergear.h"
                        )
                        self._plugin_manager.send_plugin_message(
                            "mgsetup",
                            dict(
                                commandResponse="Copied the Dual configuration to Configuration_makergear.h"
                            ),
                        )
                    except IOError as e:
                        self._logger.info(
                            "Tried to copy Dual configuration but encountered an error!"
                        )
                        self._logger.info("Error: " + str(e))
                        self._plugin_manager.send_plugin_message(
                            "mgsetup",
                            dict(
                                commandError="Tried to copy Dual configuration but encountered an error!  Error: "
                                + str(e)
                            ),
                        )
                else:
                    try:
                        shutil.copyfile(
                            "/home/pi/m3firmware/src/Marlin/Configuration_makergear.h.m3SE",
                            "/home/pi/m3firmware/src/Marlin/Configuration_makergear.h",
                        )
                        self._logger.info(
                            "Copied the Single configuration to Configuration_makergear.h"
                        )
                        self._plugin_manager.send_plugin_message(
                            "mgsetup",
                            dict(
                                commandResponse="Copied the Single configuration to Configuration_makergear.h"
                            ),
                        )
                    except IOError as e:
                        self._logger.info(
                            "Tried to copy Single configuration but encountered an error!"
                        )
                        self._logger.info("Error: " + str(e))
                        self._plugin_manager.send_plugin_message(
                            "mgsetup",
                            dict(
                                commandError="Tried to copy Single configuration but encountered an error!  Error: "
                                + str(e)
                            ),
                        )

            else:

                # self._logger.info(self._printer_profile_manager.get_current_or_default()["extruder"]["count"])
                self.active_profile = (
                    self._printer_profile_manager.get_current_or_default()["model"]
                )
                # self._logger.info(self._printer_profile_manager.get_current_or_default()["model"])
                self._logger.info("Profile: " + self.active_profile)

                new_profile_string = (re.sub("[^\w]", "_", self.active_profile)).upper()

                with open(
                    "/home/pi/m3firmware/src/Marlin/Configuration_makergear.h", "r+"
                ) as f:
                    time_string = str(
                        datetime.datetime.now().strftime("%y-%m-%d.%H:%M")
                    )
                    old_config = f.read()
                    f.seek(0, 0)
                    if f.readline() == "\n":
                        f.seek(0, 0)
                        f.write(
                            "#define MAKERGEAR_MODEL_"
                            + new_profile_string
                            + "//AUTOMATICALLY FILLED BY MGSETUP PLUGIN - "
                            + time_string
                            + "\n"
                            + old_config
                        )
                    else:
                        f.seek(0, 0)
                        old_line = f.readline()
                        f.seek(0, 0)
                        i = old_config.index("\n")
                        old_config_stripped = old_config[i + 1 :]
                        f.write(
                            "#define MAKERGEAR_MODEL_"
                            + new_profile_string
                            + "//AUTOMATICALLY FILLED BY MGSETUP PLUGIN - "
                            + time_string
                            + "\n"
                            + "// "
                            + old_line
                            + "// OLD LINE BACKED UP - "
                            + time_string
                            + "\n"
                            + old_config_stripped
                        )

            self.get_local_firmware_version()

        else:
            self._logger.info(
                "Tried to update firmware, but lock file exists!  Aborting."
            )
            self._plugin_manager.send_plugin_message(
                "mgsetup",
                dict(
                    commandError="Tried to update firmware, but lock file exists!  Aborting."
                ),
            )

        # settings.printerProfiles.currentProfileData().extruder.count()

    # octoprint.settings.Settings.set(octoprint.settings.settings(),["appearance", "name"],["MakerGear " +self.newhost])

    def write_netconnectd_password(self, new_password):
        subprocess.call(
            self.script_path("changeNetconnectdPassword.sh") + new_password["password"],
            shell=True,
        )
        self._logger.info(
            "Netconnectd password changed to " + new_password["password"] + " !"
        )

    def change_hostname(self, new_hostname):
        subprocess.call(
            self.script_path("changeHostname.sh")
            + new_hostname["hostname"]
            + " "
            + self.newhost,
            shell=True,
        )
        self._logger.info("Hostname changed to " + new_hostname["hostname"] + " !")

    def request_values(self):
        self._printer.commands(["M503"])

    def send_current_values(self):
        self.printer_value_version = time.time()
        self._plugin_manager.send_plugin_message(
            "mgsetup",
            dict(
                zoffsetline=self.zoffsetline,
                tooloffsetline=self.tooloffsetline,
                firmwareline=self.firmwareline,
                probeOffsetLine=self.probe_offset_line,
                printerValueVersion=self.printer_value_version,
            ),
        )

    def send_values(self, client_version=-1):
        if client_version == self.printer_value_version:
            return
        elif self.printer_value_good:
            self.send_current_values()
        else:
            self.request_values()

    def get_api_commands(self):
        self._logger.info("MGSetup get_api_commands triggered.")
        # self._logger.info("M114 sent to printer.")
        # self._printer.commands("M114");
        # self.position_state = "stale"
        return dict(
            turnSshOn=[],
            turnSshOff=[],
            adminAction=["action"],
            writeNetconnectdPassword=["password"],
            changeHostname=["hostname"],
            sendSerial=[],
            storeActivation=["activation"],
            checkActivation=["userActivation"],
            remindLater=[],
            checkGoogle=["url"],
            flushPrintActive=[],
            mgLog=["stringToLog", "priority"],
            sendValues=["clientVersion"],
        )

    def on_api_get(self, request):
        self._logger.info("MGSetup on_api_get triggered.")
        return flask.jsonify(
            dict(
                currentposition=self.current_position, positionstate=self.position_state
            )
        )
        self.position_state = "stale"

    def process_z_offset(self, comm, line, *args, **kwargs):

        if "Error: " in line:
            self._logger.info("process_z_offset triggered - Error !")
            self._plugin_manager.send_plugin_message("mgsetup", dict(mgerrorline=line))
        if "Warning: " in line:
            self._logger.info("process_z_offset triggered - Warning !")
            self._plugin_manager.send_plugin_message("mgsetup", dict(mgwarnline=line))

        if self.print_active:
            # self._logger.debug("printActive true, skipping filters.")
            # self._logger.info("printActive true, skipping filters - info")
            return line

        # if "M206" not in line and "M218" not in line and "FIRMWARE_NAME" not in line and "Error" not in line and "z_min" not in line and "Bed X:" not in line and "M851" not in line:
        # 	return line
        new_values_present = False
        watch_commands = [
            "M206",
            "M218",
            "FIRMWARE_NAME",
            "Error",
            "z_min",
            "Bed X:",
            "M851",
            "= [[ ",
            "Settings Stored",
        ]

        if not any([x in line for x in watch_commands]):
            return line

        # if ("M206" or "M218" or "FIRMWARE_NAME" or "Error" or "z_min" or "Bed X:" or "M851" or "= [[ ") not in line:
        # 	return line

        # logging.getLogger("octoprint.plugin." + __name__ + "process_z_offset triggered")
        if "MGERR" in line:
            self._logger.info("process_z_offset triggered - MGERR !")
            self._plugin_manager.send_plugin_message("mgsetup", dict(mgerrorline=line))

        if "M206" in line:
            self._logger.info("process_z_offset triggered - Z offset")
            self.zoffsetline = line
            self._plugin_manager.send_plugin_message("mgsetup", dict(zoffsetline=line))
            new_values_present = True

        if "M218" in line:
            self._logger.info("process_z_offset triggered - Tool offset")
            self.tooloffsetline = line
            self._plugin_manager.send_plugin_message(
                "mgsetup", dict(tooloffsetline=line)
            )
            new_values_present = True

        # __plugin_implementation__._logger.info(line)

        if "FIRMWARE_NAME" in line:
            self._logger.info("plugin version - firmware reports itself as: ")
            self.firmwareline = line
            self._plugin_manager.send_plugin_message("mgsetup", dict(firmwareline=line))

        if "Error:Probing failed" in line:
            self._logger.info("'Error:Probing failed' message received")
            self._plugin_manager.send_plugin_message("mgsetup", dict(errorline=line))
            return ""

        if "z_min" in line:
            self._logger.info("z_min message received")
            self._plugin_manager.send_plugin_message("mgsetup", dict(zminline=line))

        if "Bed X:" in line:
            self._logger.info("Bed Probe data received?")
            self._plugin_manager.send_plugin_message("mgsetup", dict(probeline=line))

        if "M851" in line:
            self._logger.info("Z Probe Offset received")
            self.probe_offset_line = line
            self._plugin_manager.send_plugin_message(
                "mgsetup", dict(probeOffsetLine=line)
            )
            new_values_present = True

        if "= [[ " in line:
            self._logger.info("Bed Leveling Information received")
            self._plugin_manager.send_plugin_message("mgsetup", dict(bedLevelLine=line))

        if "Settings Stored" in line:
            self._logger.info(
                "Looks like a M500 was sent from somewhere.  Sending a M503 to check current values."
            )
            self.request_values()

        if new_values_present:
            self.printer_value_good = True
            self.send_values()

        return line

    def reset_registration(self):
        try:  # a bunch of code with minor error checking and user alert...ion to copy scripts to the right location; should only ever need to be run once
            os.makedirs("/home/pi/.mgsetup")
        except OSError:
            if not os.path.isdir("/home/pi/.mgsetup"):
                raise
        f = open("/home/pi/.mgsetup/actkey", "w")
        f.write("")
        f.close()
        self._settings.set(["registered"], False)
        self._settings.set(["activated"], False)
        self._settings.save()
        self._logger.info("Activation and Registration Reset!")

    def disable_radios(self):
        self._execute("netconnectcli stop_ap")
        if not os.path.isfile("/boot/config.txt.backup"):
            self._execute("sudo cp /boot/config.txt /boot/config.txt.backup")
            self._plugin_manager.send_plugin_message(
                "mgsetup",
                dict(commandResponse="Copied config.txt to config.txt.backup ."),
            )
        if not "dtoverlay=pi3-disable-wifi" in open("/boot/config.txt"):
            # f = open('/boot/config.txt', 'a')
            # f.write("\ndtoverlay=pi3-disable-wifi")
            # f.close()
            self._execute(
                "sudo cp /home/pi/oprint/local/lib/python2.7/site-packages/octoprint_mgsetup/static/maintenance/scripts/config.txt.wifiDisable /boot/config.txt"
            )
            self._plugin_manager.send_plugin_message(
                "mgsetup",
                dict(
                    commandResponse="Copied config.txt.wifiDisable to config.txt to Disable Wifi.  Will now reboot."
                ),
            )
            self._execute("sudo reboot")

    def enable_radios(self):
        # if "dtoverlay=pi3-disable-wifi" in open('/boot/config.txt'):
        self._execute("sudo cp /boot/config.txt.backup /boot/config.txt")
        self._plugin_manager.send_plugin_message(
            "mgsetup",
            dict(
                commandResponse="Copied config.txt.backup to config.txt .  Will now reboot."
            ),
        )
        self._execute("sudo reboot")

    def disable_smb(self):
        # if "dtoverlay=pi3-disable-wifi" in open('/boot/config.txt'):
        self._execute("sudo systemctl disable smbd")

    def enable_smb(self):
        # if "dtoverlay=pi3-disable-wifi" in open('/boot/config.txt'):
        self._execute("sudo systemctl emable smbd")

    def patch_smb(self):
        # if "dtoverlay=pi3-disable-wifi" in open('/boot/config.txt'):

        self._execute('echo "Patching SMB"')
        self._execute(
            "sudo cp "
            + self._basefolder
            + "/static/maintenance/system/smbPatched.conf /etc/samba/smb.conf"
        )
        self._execute("sudo chmod 644 /etc/samba/smb.conf")
        self._execute("sudo chown root /etc/samba/smb.conf")
        self._execute("sudo service smbd restart")
        self._execute('echo "Patch Finished"')

    def lock_firmware(self):
        if not os.path.isfile("/home/pi/m3firmware/src/Marlin/lockFirmware"):
            open("/home/pi/m3firmware/src/Marlin/lockFirmware", "a").close()
            self._logger.info("Firmware lock file created.")
            self._plugin_manager.send_plugin_message(
                "mgsetup", dict(commandError="Firmware lock file created!")
            )

    def unlock_firmware(self):
        if os.path.isfile("/home/pi/m3firmware/src/Marlin/lockFirmware"):
            try:
                os.remove("/home/pi/m3firmware/src/Marlin/lockFirmware")
                self._logger.info("Firmware lock file deleted.")
                self._plugin_manager.send_plugin_message(
                    "mgsetup",
                    dict(
                        commandError="Firmware lock file deleted - now free to update firmware."
                    ),
                )
            except IOError as e:
                self._logger.info(
                    "Tried to delete firmware lock file, but there was an error!"
                )
                self._logger.info("Error: " + str(e))
                self._plugin_manager.send_plugin_message(
                    "mgsetup",
                    dict(
                        commandError="Tried to delete firmware lock file but encountered an error!  Error: "
                        + str(e)
                    ),
                )
        else:
            self._logger.info(
                "Tried to delete firmware lock file, but it doesn't seem to exist?"
            )
            self._plugin_manager.send_plugin_message(
                "mgsetup",
                dict(
                    commandError="Tried to delete firmware lock file, but it doesn't seem to exist?"
                ),
            )

    def admin_action(self, action, payload={}):
        self._logger.info("adminAction called: " + str(action))
        if action["action"] == "turnSshOn":
            # self.turn_ssh_on()
            self._execute(self.script_path("startSsh.sh"))
            self._logger.info("SSH service started!")
            self.admin_action(dict(action="ssh_state"))
        elif action["action"] == "turnSshOff":
            # self.turn_ssh_off()
            self._execute(self.script_path("stopSsh.sh"))
            self._logger.info("SSH service stopped!")
            self.admin_action(dict(action="ssh_state"))
        elif action["action"] == "resetWifi":
            # subprocess.call(self.script_path("resetWifi.sh"))
            self._execute(self.script_path("resetWifi.sh"))
            self._logger.info("Wifi reset!")
        elif action["action"] == "uploadFirmware":
            # subprocess.call(self.script_path("upload.sh"))

            self._printer.cancel_print()
            self._printer.disconnect()
            self.mg_log(
                self._execute("python /home/pi/.octoprint/scripts/upload.py"), 2
            )
            self._printer.connect()

        elif action["action"] == "uploadAndFlashFirmware":

            self.update_local_firmware()

            self._printer.cancel_print()
            self._printer.disconnect()
            self.mg_log(
                self._execute("python /home/pi/.octoprint/scripts/upload.py"), 2
            )
            self._printer.connect()

        elif action["action"] == "counterTest":
            self.counter_test(action)
        elif action["action"] == "expandFilesystem":
            # subprocess.call(self.script_path("expandFilesystem.sh"), shell=True)
            self._execute(self.script_path("expandFilesystem.sh"))
            self._logger.info("Filesystem expanded - will reboot now.")
        elif action["action"] == "resetRegistration":
            self._logger.info("Registration reset!")
            self.reset_registration()
        elif action["action"] == "patch":
            self._logger.info("Patch started.")
            self._execute(
                "/home/pi/oprint/local/lib/python2.7/site-packages/octoprint_mgsetup/static/patch/patch.sh"
            )
        elif action["action"] == "updateFirmware":
            self.update_local_firmware()
        elif action["action"] == "showIfconfig":
            self._logger.info("Showing ifconfig / netconnectcli status.")
            self._execute("ifconfig")
            self._execute("netconnectcli status")
        elif action["action"] == "ps":
            self._logger.info("Showing ps.")
            self._execute("ps -eF")
        elif action["action"] == "routen":
            self._logger.info("Showing route -n.")
            self._execute("route -n")
        elif action["action"] == "whead":
            self._logger.info("Showing w | head -n1.")
            self._execute("w | head -n1")
        elif action["action"] == "lockFirmware":
            self.lock_firmware()
        elif action["action"] == "unlockFirmware":
            self.unlock_firmware()
        elif action["action"] == "disableRadios":
            self.disable_radios()
        elif action["action"] == "enableRadios":
            self.enable_radios()
        elif action["action"] == "disableSmb":
            self.disable_smb()
        elif action["action"] == "enableSmb":
            self.enable_smb()
        elif action["action"] == "patchSmb":
            self.patch_smb()
        elif action["action"] == "flushPrintActive":
            self.print_active = False
            self.mg_log("flushPrintActive called", 0)
        elif action["action"] == "collectLogs":
            self.collect_logs()
            self.mg_log("collectLogs called", 0)
            return "collectLogs called"

        elif action["action"] == "ssh_state":
            self._logger.info("Showing sudo service ssh status.")
            ssh_state = self._execute("sudo service ssh status")
            self._logger.info(ssh_state)
            if "Active: active" in str(ssh_state[1]):
                self._logger.info("Active: active in ssh_state")
                self._settings.set(["sshOn"], True)
                self._settings.save()
            else:
                self._logger.info("Active: active not in ssh_state")
                self._settings.set(["sshOn"], False)
                self._settings.save()

        elif action["action"] == "logpatch":
            # "/home/pi/OctoPrint/venv/bin/OctoPrint_Mgsetup/octoprint_mgsetup/static/patch/logpatch.sh"
            # self._execute("/home/pi/OctoPrint/venv/bin/OctoPrint-Mgsetup/octoprint_mgsetup/static/patch/logpatch.sh")
            # self._execute("/home/pi/oprint/local/lib/python2.7/site-packages/octoprint_mgsetup/static/patch/logpatch.sh")
            self._logger.info("Logpatch started.")

            # subprocess.call("/home/pi/oprint/local/lib/python2.7/site-packages/octoprint_mgsetup/static/patch/logpatch.sh")
            self.mg_log(
                self._execute(
                    "/home/pi/oprint/local/lib/python2.7/site-packages/octoprint_mgsetup/static/patch/logpatch.sh"
                ),
                2,
            )

            # if not os.path.isfile("/home/pi/.octoprint/logs/dmesg"):
            # 	if os.path.isfile("/var/log/dmesg"):
            # 		try:
            # 			os.symlink("/var/log/dmesg","/home/pi/.octoprint/logs/dmesg")
            # 		except OSError:
            # 			if os.path.isfile("/var/log/dmesg"):
            # 				raise
            # if not os.path.isfile("/home/pi/.octoprint/logs/messages"):
            # 	if os.path.isfile("/var/log/messages"):
            # 		try:
            # 			os.symlink("/var/log/messages","/home/pi/.octoprint/logs/messages")
            # 		except OSError:
            # 			if os.path.isfile("/var/log/messages"):
            # 				raise
            # if not os.path.isfile("/home/pi/.octoprint/logs/syslog"):
            # 	if os.path.isfile("/var/log/syslog"):
            # 		try:
            # 			os.symlink("/var/log/syslog","/home/pi/.octoprint/logs/syslog")
            # 		except OSError:
            # 			if os.path.isfile("/var/log/syslog"):
            # 				raise
            # if not os.path.isfile("/home/pi/.octoprint/logs/syslog.1"):
            # 	if os.path.isfile("/var/log/syslog.1"):
            # 		try:
            # 			os.symlink("/var/log/syslog.1","/home/pi/.octoprint/logs/syslog.1")
            # 		except OSError:
            # 			if os.path.isfile("/var/log/syslog.1"):
            # 				raise
            # if not os.path.isfile("/home/pi/.octoprint/logs/netconnectd.log"):
            # 	if os.path.isfile("/var/log/netconnectd.log"):
            # 		try:
            # 			os.symlink("/var/log/netconnectd.log","/home/pi/.octoprint/logs/netconnectd.log")
            # 		except OSError:
            # 			if os.path.isfile("/var/log/netconnectd.log"):
            # 				raise
            # if not os.path.isfile("/home/pi/.octoprint/logs/netconnectd.log.1"):
            # 	if os.path.isfile("/var/log/netconnectd.log.1"):
            # 		try:
            # 			os.symlink("/var/log/netconnectd.log.1","/home/pi/.octoprint/logs/netconnectd.log.1")
            # 		except OSError:
            # 			if os.path.isfile("/var/log/netconnectd.log.1"):
            # 				raise

        # elif action["action"] == "setCurrentTest":
        # 	self.current_project_print_success_time = 0
        # 	if
        # 	self.current_project_name =
        # 	self._settings.set(["currentProjectPrintSuccessTime"],self.current_project_print_success_time)
        # 	self._settings.save()

        elif action["action"] == "resetCurrentProject":
            self._logger.info("newProjectName:")
            self._logger.info(action["payload"]["newProjectName"])
            if "newProjectName" in action["payload"]:
                self.current_project_name = action["payload"]["newProjectName"]
            else:
                self.current_project_name = ""
            self.current_project_print_success_time = 0
            self.current_project_print_fail_time = 0
            self.current_project_machine_fail_time = 0
            self._settings.set(
                ["currentProjectPrintSuccessTime"],
                self.current_project_print_success_time,
            )
            self._settings.set(
                ["currentProjectPrintFailTime"], self.current_project_print_fail_time
            )
            self._settings.set(
                ["currentProjectMachineFailTime"],
                self.current_project_machine_fail_time,
            )
            self._settings.set(["currentProjectName"], self.current_project_name)

            self._settings.save()
            self.trigger_settings_update()

        elif action["action"] == "printerUpgrade":
            self.printer_upgrade(action["payload"])

    def printer_upgrade(self, upgrade_info):
        self._logger.info("printerUpgrade debug position 1.")
        if upgrade_info["upgradeType"] == None:
            self._plugin_manager.send_plugin_message(
                "mgsetup",
                dict(commandError="Unknown upgrade / no upgrade chosen, canceling.\n"),
            )
            return
        # self._plugin_manager.send_plugin_message("mgsetup", dict(commandResponse = "Starting the Upgrade process.\n"))

        if upgrade_info["upgradeType"] == "idRev0toRev1":
            self._logger.info("printerUpgrade debug position 2.")

            # self._printer.disconnect()
            # self._plugin_manager.send_plugin_message("mgsetup", dict(commandResponse = "Printer disconnected.\n"))
            try:
                new_profile = dict(
                    name="M3-ID-Rev1-000",
                    color="default",
                    axes=dict(
                        y=dict(speed=12000, inverted=True),
                        x=dict(speed=12000, inverted=False),
                        z=dict(speed=1200, inverted=False),
                        e=dict(speed=400, inverted=False),
                    ),
                    heatedBed=True,
                    volume=dict(
                        origin="lowerleft",
                        formFactor="rectangular",
                        depth=250.0,
                        width=200.0,
                        custom_box=dict(
                            z_min=0.0,
                            y_min=0.0,
                            x_max=240.0,
                            x_min=0.0,
                            y_max=250.0,
                            z_max=205.0,
                        ),
                        height=200.0,
                    ),
                    model="M3-ID-Rev1-000",
                    id="makergear_m3_independent_dual",
                    extruder=dict(
                        count=2,
                        nozzleDiameter=0.35,
                        offsets=[(0.0, 0.0), (0.0, 0.0)],
                        sharedNozzle=False,
                    ),
                )
                self._printer_profile_manager.save(new_profile, True, True)
                self._printer_profile_manager.select(new_profile["name"])
                self._plugin_manager.send_plugin_message(
                    "mgsetup",
                    dict(commandResponse="New profile created and selected.\n"),
                )
                self.trigger_settings_update()
                self._logger.info("printerUpgrade debug position 3.")

            except Exception as e:
                self._logger.info(
                    "Failed upgrade while creating profile, error: " + str(e)
                )
                self._plugin_manager.send_plugin_message(
                    "mgsetup",
                    dict(
                        commandError="Error while creating profile.  Please try again or contact Support.\n"
                    ),
                )
                self._plugin_manager.send_plugin_message(
                    "mgsetup", dict(softwareUpgraded=False)
                )

                return

            try:
                self._logger.info("printerUpgrade debug position 4.")

                self._plugin_manager.send_plugin_message(
                    "mgsetup",
                    dict(commandResponse="Switching to new firmware and uploading.\n"),
                )
                self._logger.info(
                    self._execute(
                        "git -C /home/pi/m3firmware/src fetch --all; git -C /home/pi/m3firmware/src reset --hard; git -C /home/pi/m3firmware/src pull; git -C /home/pi/m3firmware/src checkout 1.1.6"
                    )
                )
                self._logger.info("printerUpgrade debug position 5.")

                new_profile_string = (
                    re.sub("[^\w]", "_", new_profile["model"])
                ).upper()

                with open(
                    "/home/pi/m3firmware/src/Marlin/Configuration_makergear.h", "r+"
                ) as f:
                    time_string = str(
                        datetime.datetime.now().strftime("%y-%m-%d.%H:%M")
                    )
                    old_config = f.read()
                    f.seek(0, 0)
                    if f.readline() == "\n":
                        f.seek(0, 0)
                        f.write(
                            "#define MAKERGEAR_MODEL_"
                            + new_profile_string
                            + "//AUTOMATICALLY FILLED BY MGSETUP PLUGIN - "
                            + time_string
                            + "\n"
                            + old_config
                        )
                    else:
                        f.seek(0, 0)
                        old_line = f.readline()
                        f.seek(0, 0)
                        i = old_config.index("\n")
                        old_config_stripped = old_config[i + 1 :]
                        f.write(
                            "#define MAKERGEAR_MODEL_"
                            + new_profile_string
                            + "//AUTOMATICALLY FILLED BY MGSETUP PLUGIN - "
                            + time_string
                            + "\n"
                            + "// "
                            + old_line
                            + "// OLD LINE BACKED UP - "
                            + time_string
                            + "\n"
                            + old_config_stripped
                        )

                self.mg_log(
                    self._execute("python /home/pi/.octoprint/scripts/upload.py"), 2
                )
                self._plugin_manager.send_plugin_message(
                    "mgsetup", dict(commandResponse="Reconnecting to printer.\n")
                )
                self._printer.connect()
                self._plugin_manager.send_plugin_message(
                    "mgsetup", dict(commandResponse="Resetting firmware values.\n")
                )
                self._printer.commands(["M502", "M500"])
                self._logger.info("printerUpgrade debug position 6.")

            except Exception as e:
                self._logger.info(
                    "Failed upgrade while trying to change firmware, error: " + str(e)
                )
                self._plugin_manager.send_plugin_message(
                    "mgsetup",
                    dict(
                        commandError="Error while switching / uploading firmware.  Please try again or contact Support.\n"
                    ),
                )
                self._plugin_manager.send_plugin_message(
                    "mgsetup", dict(softwareUpgraded=False)
                )

                return

            self._logger.info("printerUpgrade debug position 7.")

            # self._plugin_manager.send_plugin_message("mgsetup", dict(commandResponse = "Software upgrade for M3 ID Rev0 to Rev1 complete.  Perform the full Quick Check to calibrate your printer.\n"))
            self._plugin_manager.send_plugin_message(
                "mgsetup",
                dict(
                    commandResponse="Please contact Support if you have any issues.\n"
                ),
            )
            self._plugin_manager.send_plugin_message(
                "mgsetup", dict(softwareUpgraded=True)
            )
            self._logger.info("printerUpgrade debug position 8.")

    def turn_ssh_on(self):
        subprocess.call(self.script_path("startSsh.sh"))
        self._logger.info("SSH service started!")
        self.admin_action(dict(action="sshState"))

    def turn_ssh_off(self):
        subprocess.call(self.script_path("stopSsh.sh"))
        self._logger.info("SSH service stopped!")
        self.admin_action(dict(action="sshState"))

    def on_api_command(self, command, data):
        self._logger.info(
            "MGSetup on_api_command triggered.  Command: "
            + str(command)
            + " .  Data: "
            + str(data)
        )
        if command == "turnSshOn":
            self.turn_ssh_on()
        elif command == "turnSshOff":
            self.turn_ssh_off()
        elif command == "adminAction":
            self.admin_action(data)
        elif command == "writeNetconnectdPassword":
            # self.write_netconnectd_password(data)
            self._execute(
                self.script_path("changeNetconnectdPassword.sh") + data["password"]
            )
            self._logger.info(
                "Netconnectd password changed to " + data["password"] + " !"
            )
        elif command == "changeHostname":
            # self.change_hostname(data)
            self._execute(
                self.script_path("changeHostname.sh")
                + data["hostname"]
                + " "
                + self.newhost
            )
            self._logger.info("Hostname changed to " + data["hostname"] + " !")
        elif command == "storeActivation":
            self.store_activation(data)
        elif command == "checkActivation":
            self.check_activation(data)
        elif command == "remindLater":
            self.remind_later()
        elif command == "checkGoogle":
            self.check_internet(3, 3, data["url"])
        elif command == "flushPrintActive":
            self.print_active = False
            self._logger.info("flushPrintActive executed.")
        elif command == "mgLog":
            self.mg_log(data["stringToLog"], data["priority"])
        elif command == "sendValues":
            self.send_values(data["clientVersion"])

    def send_serial(self):
        self._logger.info("MGSetup sendSerial triggered.")
        self._plugin_manager.send_plugin_message("mgsetup", dict(serial=self.serial))

    def store_activation(self, activation):
        self._logger.info(activation)
        try:  # a bunch of code with minor error checking and user alert...ion to copy scripts to the right location; should only ever need to be run once
            os.makedirs("/home/pi/.mgsetup")
        except OSError:
            if not os.path.isdir("/home/pi/.mgsetup"):
                raise
        f = open("/home/pi/.mgsetup/actkey", "w")
        f.write(activation["activation"])
        f.close()
        self._settings.set(["registered"], True)
        self._settings.save()

    def check_activation(self, user_activation):
        with open("/home/pi/.mgsetup/actkey", "r") as f:
            self.activation = f.readline().strip()
            if self.activation == user_activation["user_activation"]:
                self._logger.info("Activation successful!")
                self._settings.set(["activated"], True)
                self._settings.save()
                self._plugin_manager.send_plugin_message(
                    "mgsetup", "activation success"
                )
            else:
                self._logger.info("Activation failed!")
                self._plugin_manager.send_plugin_message("mgsetup", "activation failed")

    ##plugin auto update
    def get_version(self):
        self._logger.info("MGSetup get_version triggered.")
        return self._plugin_version

    def get_update_information(self):
        self._logger.info("MGSetup get_update_information triggered.")
        if self.plugin_version == "master":
            return dict(
                octoprint_mgsetup=dict(
                    displayName="Makergear Setup",
                    displayVersion=self._plugin_version,
                    # version check: github repository
                    type="github_release",
                    user="MakerGear",
                    repo="MakerGear_OctoPrint_Setup",
                    current=self._plugin_version,
                    release_branch="master",
                    # update method: pip
                    pip="https://github.com/MakerGear/MakerGear_OctoPrint_Setup/archive/{target_version}.zip",
                )
            )
        if self.plugin_version == "refactor":
            return dict(
                octoprint_mgsetup=dict(
                    displayName="Makergear Setup",
                    displayVersion=self._plugin_version,
                    # version check: github repository
                    type="github_release",
                    user="MakerGear",
                    repo="MakerGear_OctoPrint_Setup",
                    current=self._plugin_version,
                    release_branch="refactor",
                    prerelease=True,
                    # update method: pip
                    pip="https://github.com/MakerGear/MakerGear_OctoPrint_Setup/archive/{target_version}.zip",
                )
            )

    def route_hook(self, server_routes, *args, **kwargs):
        from octoprint.server.util.tornado import (
            LargeResponseHandler,
            UrlProxyHandler,
            path_validation_factory,
        )
        from octoprint.util import is_hidden_path

        self._logger.info("route_hook triggered!")
        # self._logger.info(server_routes)

        return [
            (
                r"/video/(.*)",
                LargeResponseHandler,
                dict(
                    path=self._basefolder + "/video",
                    as_attachment=True,
                    path_validation=path_validation_factory(
                        lambda path: not is_hidden_path(path), status_code=404
                    ),
                ),
            )
        ]

    def copy_maintenance_files(self, src, dest):
        src_dir = os.path.join(self._basefolder, "static/maintenance", src)
        src_files = os.listdir(src_dir)
        dest_dir = os.path.join(self._settings.getBaseFolder("base"), dest)

        # src_files = os.listdir(self._basefolder + "/static/maintenance/gcode")
        # src = self._basefolder + "/static/maintenance/gcode"
        # dest = self.script_path("gcode")
        for file_name in src_files:
            full_src_name = os.path.join(src_dir, file_name)
            full_dest_name = os.path.join(dest_dir, file_name)
            if not (os.path.isfile(full_dest_name)):
                shutil.copy(full_src_name, dest_dir)
                self._logger.info("Had to copy " + file_name + " to scripts folder.")
            else:
                if (
                    hashlib.md5(open(full_src_name).read().encode("utf-8")).hexdigest()
                ) != (
                    hashlib.md5(open(full_dest_name).read().encode("utf-8")).hexdigest()
                ):
                    shutil.copy(full_src_name, dest_dir)
                    self._logger.info(
                        "Had to overwrite " + file_name + " with new version."
                    )

    def script_path(self, file):
        base = self._settings.getBaseFolder("scripts")
        return os.path.join(base, file)
