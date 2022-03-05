# ArcClimate

ArcClimate (hereinafter referred to as "AC") is based on a mesoscale numerical prediction model (hereinafter referred to as "MSM") produced by the Japan Meteorological Agency for temperature, humidity, horizontal full-sky solar radiation, downward atmospheric radiation, wind direction and wind speed, which are necessary for estimating the heat load of buildings, and can be used to estimate the heat load of any specified building through elevation correction and spatial interpolation. The program produces a meteorological data set for design purposes for a location.

AC automatically downloads the data necessary to create a specified arbitrary point from data that has been pre-calculated and stored in the cloud (hereinafter referred to as "basic data set"), and creates a design meteorological data set for an arbitrary point by performing spatial interpolation calculations on these data.

![ArcClimate Flow of creating meteorological data](flow.png "Flow of creating meteorological data")

The area for which data can be generated ranges from 22.4 to 47.6°N and 120 to 150°E, including almost all of Japan's land area (Note 1). The data can be generated for a 10-year period from January 1, 2011 to December 31, 2020 (Japan Standard Time). 10 years of data or one year of extended AMeDAS data (hereinafter referred to as "EA data") generated from 10 years of data can be obtained.

Note1: Remote islands such as Okinotori-shima (southernmost point: 20.42°N, 136.07°E) and Minamitori-shima (easternmost point: 24.28°N, 153.99°E) are not included. In addition, some points cannot be calculated if the surrounding area is almost entirely ocean (elevation is less than 0 m).

*Read this in other languages: [English](README.md), [日本語](README.ja.md).*

## Usage Environment 

[Python](htts://www.python.org/) 3.8 is assumed.
Quick Start assumes Ubuntu, but it also works on Windows. For example, `python` instead of `python3` or `pip` instead of `pip3` may be used. Please change the reading according to your environment.


## Quick Start

The following command will generate a standard year weather data file for the specified latitude and longitude point.

```
$ pip3 install git+https://github.com/DEE-BRI/arcclimate.git
$ arcclimate 36.1290111 140.0754174 -o kenken_EA.csv --mode EA 
```

You can specify any longitude and latitude in Japan.
The latitude and longitude of an arbitrary point can be obtained from GoogleMap or other sources.
For example, if you search for the National Research Institute for Architectural Science in GoogleMap, the URL will be
``https://www.google.co.jp/maps/place/国立研究開発法人建築研究/@36.1290111,140.0754174.... The result will be something like ````.
In this URL, 36.1290111 is latitude and 140.0754174 is longitude.

Enter the latitude and longitude information obtained on the command line and run the program.
```
$ arcclimate 36.1290111 140.0754174 -o weather.csv
```

After the necessary data is retrieved from the network, the correction process is executed.
The results are saved in `weather.csv`.

## Output CSV items

1. date ... Reference time. JST (Japan Standard Time). Except for the average year, which is displayed as 1970.
2. tmp ... Instantaneous value of temperature at the reference time (unit: °C)
3. MR ... Instantaneous value of absolute humidity by weight at the reference time (unit: g/kgDA)
4. DSWRF_est ... Estimated total solar radiation for the hour before the reference time (unit: MJ/m2)
5. DSWRF_msm ... Totalized solar radiation for the hour before the reference time (unit: MJ/m2)
6. Ld ... Total downward atmospheric radiation for the hour before the reference time (unit: MJ/m2)
7. VGRD ... North-south wind (V-axis) (unit: m/s)
8. UGRD ... East-west wind (U-axis) (unit: m/s)
9. PRES ... Barometric pressure (unit: hPa)
10. APCP01 ... Accumulated precipitation for the hour before the reference time (unit: mm/h)
11. w_spd ... Instantaneous wind speed at the reference time (unit: m/s)
12. w_dir ... Instantaneous value of wind direction at the reference time (unit: °)

## Author

ArcClimate Development Team

## License

Distributed under the MIT License. See [LICENSE](LICENSE.txt) for more information.

## Acknowledgement

This is a programmed version of the construction method that is a product of the Building Standard Development Promotion Project E12, "Study to Detail Climatic Conditions Assumed for Assessment of Energy Consumption Performance.

