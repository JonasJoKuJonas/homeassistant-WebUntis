# WebUntis
<!--
[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs)
-->
![Version](https://img.shields.io/github/v/release/JonasJoKuJonas/homeassistant-WebUntis)
![Downloads](https://img.shields.io/github/downloads/JonasJoKuJonas/homeassistant-WebUntis/total)

Custom component to access data from Web Untis in Home Assistant

## Installation

### HACS

This component is easiest installed using [HACS](https://github.com/custom-components/hacs).

### Manual installation

Copy all files from custom_components/webuntis/ to custom_components/webuntis/ inside your config Home Assistant directory.


## Configuration

### Server & School
Visit https://webuntis.com and click on your school.

In the URL you should find the information you need:
```
https://demo.webuntis.com/WebUntis/?school=Demo-School#/basic/login
        ^^^^^^^^^^^^^^^^^                  ^^^^^^^^^^^
              Server                          School
```
