import xml.etree.cElementTree as ET
import isodate
import datetime
import pytz
import logging

import util
import data

# Vraag een logger object:
__logger__ = logging.getLogger(__name__)

def parse_arnu_message(data, iff):
    # Parse XML:
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exception:
        __logger__.error("Can't parse ARNU XML message: %s", exception)
        return None

    # Zoek belangrijke nodes op:
    service_info_lijst = root.find('ServiceInfoList')
    service_info_items = service_info_lijst.findall('ServiceInfo')

    services = []

    for service_info_item in service_info_items:
        services.append(parse_arnu_service(service_info_item, iff))

    return services

def parse_arnu_service(service_info, iff):
    service = data.Service()

    service.service_id = service_info.find('ServiceCode').text
    service.transport_mode = service_info.find('TransportModeCode').text
    service.transport_mode_description = iff.get_transport_mode(service.transport_mode)

    # Parse stops:
    stops = service_info.find('StopList').findall('Stop')
    previous_stop_cancelled = False

    for stop_info in stops:
        stopcode = stop_info.findtext('StopCode').lower()
        cancelled = False

        # Determine servicedate based on first stop (may include cancelled stops):
        if service.service_date == None:
            service.service_date = util.parse_iso_datetime(stop_info.findtext('Departure')).date()

        stop = data.ServiceStop(stopcode)
        stop.arrival_time = util.parse_iso_datetime(stop_info.findtext('Arrival'))
        stop.arrival_delay = util.parse_iso_delay(stop_info.findtext('ArrivalTimeDelay'))
        stop.departure_time = util.parse_iso_datetime(stop_info.findtext('Departure'))
        stop.departure_delay = util.parse_iso_delay(stop_info.findtext('DepartureTimeDelay'))
        stop.scheduled_arrival_platform = stop_info.findtext('ArrivalPlatform')
        stop.actual_arrival_platform = stop_info.findtext('ActualArrivalPlatform')
        stop.scheduled_departure_platform = stop_info.findtext('DeparturePlatform')
        stop.actual_departure_platform = stop_info.findtext('ActualDeparturePlatform')
        stop.stop_name = iff.get_station_name(stopcode)

        if 'StopType' in stop_info.attrib:
            # Check whether this stop is not cancelled:
            if stop_info.attrib['StopType'] == 'Cancelled-Stop':
                __logger__.debug('Cancelled stop %s for service %s', stopcode, service.service_id)
                cancelled = True

            # Check whether this stop is diverted:
            if stop_info.attrib['StopType'] == 'Diverted-Stop':
                __logger__.debug('Diverted stop %s for service %s', stopcode, service.service_id)
                cancelled = True

        # Set arrival to cancelled if the previous stop was cancelled
        if previous_stop_cancelled == True:
            stop.cancelled_arrival = True

        # This stop is cancelled: this service won't departure here
        if cancelled == True:
            stop.cancelled_departure = True
            previous_stop_cancelled = True

        service.stops.append(stop)

    # Check whether complete service is cancelled:
    service.cancelled = True
    for stop in service.stops:
        if stop.cancelled_departure == False:
            service.cancelled = False
            break

    return service