# -*- coding: utf-8 -*-

import logging
logger = logging.getLogger(__name__)

import os
import time
import datetime
from collections import namedtuple
from collections import Counter

from . dicom import read_metadata


def walk_image_data(path, force=False):
    """Generate information on DICOM files in a directory.

    File that cannot be read are skipped and an error message is logged.

    Parameters
    ----------
    path : unicode
        Directory to read DICOM files from.
    force : bool
        Try reading nonstandard DICOM files, typically without "PART 10" headers.

    Yields
    ------
    tuple
        Yields a pair (metadata, relpath) where metadata is a dictionary
        of extracted DICOM metadata.

    """
    n = 0
    start = time.time()

    logger.info('start processing files: %s', path)

    for root, dirs, files in os.walk(path):
        n += len(files)
        for filename in files:
            abspath = os.path.join(root, filename)
            relpath = os.path.normpath(os.path.relpath(abspath, path))
            # skip DICOMDIR since we are going to read all DICOM files anyway
            if filename == 'DICOMDIR':
                continue
            logger.debug('read file: %s', relpath)
            try:
                metadata = read_metadata(abspath, force=force)
            except IOError as e:
                logger.error('cannot read file (%s): %s', str(e), relpath)
            except dicom.filereader.InvalidDicomError as e:
                logger.error('cannot read nonstandard DICOM file: %s: %s', str(e), relpath)
            except AttributeError as e:
                logger.error('missing attribute: %s: %s', str(e), relpath)
            else:
                yield (metadata, relpath)

    elapsed = time.time() - start
    logger.info('processed %d files in %.2f s: %s', n, elapsed, path)


def report_image_data(path, force=False):
    """Find DICOM files loosely organized according to the Imagen FU2 SOPs.

    The Imagen FU2 SOPs define a precise file organization for Image Data. In
    practice we have found the SOPs are only loosely followed. A method to find
    DICOM files while adapting to local variations is to read all DICOM files,
    then filter and break them down into series based on their contents.

    This function scans the directory where we expect to find the Image Data
    of a dataset and reports series of valid DICOM files.

    Parameters
    ----------
    path : unicode
        Directory to read DICOM files from.
    force : bool
        Try reading nonstandard DICOM files, typically without "PART 10" headers.

    Returns
    -------
    dict
        The key identifies a series while the value is Series namedtuple.

    """
    Series = namedtuple('Series', ['metadata', 'images'])

    series_dict = {}

    for (metadata, relpath) in walk_image_data(path, force=True):
        # compulsory metadata
        series_uid = metadata['SeriesInstanceUID']
        image_uid = metadata['SOPInstanceUID']
        series_number = metadata['SeriesNumber']
        series_description = metadata['SeriesDescription']
        image_types = metadata['ImageType']
        if 'AcquisitionDate' in metadata:
            acquisition_date = metadata['AcquisitionDate']
            if 'AcquisitionTime' in metadata:
                acquisition_time = metadata['AcquisitionTime']
                timestamp = datetime.datetime.combine(acquisition_date,
                                                      acquisition_time)
            else:
                timestamp = datetime.datetime(acquisition_date.year,
                                              acquisition_date.month,
                                              acquisition_date.day)

        # build the dictionnary of series using 'SeriesInstanceUID' as a key
        if series_uid not in series_dict:
            metadata = {
                'SeriesNumber': Counter([series_number]),
                'SeriesDescription': Counter([series_description]),
                'ImageType': Counter(x for x in image_types),
                'MinAcquisitionDateTime': timestamp,
                'MaxAcquisitionDateTime': timestamp,
            }
            series_dict[series_uid] = Series(metadata, {image_uid: relpath})
        else:
            series_dict[series_uid].metadata['SeriesNumber'].update([series_number])
            series_dict[series_uid].metadata['SeriesDescription'].update([SeriesDescription])
            series_dict[series_uid].metadata['ImageType'].update(x for x in image_types)
            if timestamp < series_dict[series_uid].metadata['MinAcquisitionDateTime']:
                series_dict[series_uid].metadata['MinAcquisitionDateTime'] = timestamp
            if timestamp > series_dict[series_uid].metadata['MaxAcquisitionDateTime']:
                series_dict[series_uid].metadata['MaxAcquisitionDateTime'] = timestamp
            # FIXME: detect duplicate 'image_uid'?
            series_dict[series_uid].files[image_uid] = relpath

        # optional metadata
        for x in metadata:
            if x not in ('SeriesInstanceUID', 'SeriesNumber', 'SeriesDescription',
                         'SOPInstanceUID', 'ImageType',
                         'AcquisitionDate', 'AcquisitionTime'):
                if x in series_dict[series_uid].metadata:
                    series_dict[series_uid].metadata[x].update([metadata[x]])
                else:
                    series_dict[series_uid].metadata[x] = Counter([metadata[x]])

    return series_dict
