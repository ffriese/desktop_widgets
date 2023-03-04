# Desktop Widgets: Cross-Platform Desktop Widgets

![Desktop Widgets Build](https://github.com/ffriese/desktop_widgets/actions/workflows/python-app.yml/badge.svg)


## Run
```python3 desktop_widgets_core.py```

## Basic Usage:

 - ### Move & Resize Widgets:
   *Move*: Alt + Drag
 
   *Resize:* Alt + Right-Click-Drag

   <img src="https://user-images.githubusercontent.com/28440404/218315320-39f8176e-b624-4157-ad1a-7751e7467e78.gif" width="600" />

 - ### Configure Widgets:
   Right-Click (On any part of the Widget that has no other interaction method)


## Calendar Widget

The Calendar Widget is an interactive Week-Calendar, which can be connected to CalDAV Calendars.
It also features a weather chart in the background when connected to a weather provider ([tomorrow.io (formerly climacell) Free API](https://www.tomorrow.io/weather-api/)). 

### Quick Overview of basic features:
 - #### Create and Edit Events
   <img src="https://user-images.githubusercontent.com/28440404/218315401-5dad3e00-d145-4980-a233-594f93c7a153.gif" width="600" />
   <img src="https://user-images.githubusercontent.com/28440404/218315407-565f0c07-f7ff-4bbf-97ab-7c34e0b2253b.gif" width="600" />

 - #### Modify View
   <img src="https://user-images.githubusercontent.com/28440404/218316214-b789ad8c-32ad-4160-86c6-e31d02a12d69.gif" width="600" />

 - #### Change Weather Location
   <img src="https://user-images.githubusercontent.com/28440404/218316097-f94c35c3-a703-44e9-82f0-c28c1c05ff4d.gif" width="600" />

## Music Widget

The Music Widget watches the play status of a couple of supported Media-Players, tries to read the ID3-Tags (SYLT or USLT) and displays the Lyrics.

 - #### Example of synchronized lyrics read from SYLT-Tag:
   <img src="https://user-images.githubusercontent.com/28440404/218318837-b64bd861-0b01-4268-bf42-d01389398153.gif" width="600" />


 - #### Supported Players:
   - Windows:
     - Musicbee
   - Linux:
     - Spotify Desktop
     - Banshee
   - (any DBus-compatible Player can be easily implemented)
   
## Network Widget

The Network Widget shows you current connections of running processes.

 - #### Example Screenshot:
   <img src="https://user-images.githubusercontent.com/28440404/218324468-39020369-c7f2-492d-9787-5a54b34adca1.png" width="600" />
