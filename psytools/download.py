#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Download Psytools files from the Delosis server.

Retrieve authentication tokens from ~/.netrc.

==========
Attributes
==========

Output
------

PSYTOOLS_PSC1_DIR : str
    Location to download PSC1-encoded files to.

"""

PSYTOOLS_PSC1_DIR = '/tmp'  #~ '/cveda/BL/RAW/PSC1/psytools'
BASE_URL = 'https://psytools.delosis.com/psytools-server/dataservice/dataset/'
CA_BUNDLE = #~ '/cveda/delosisCA.pem'

import logging
logging.basicConfig(level=logging.INFO)

import os
import requests  # so much easier than most HTTP Python libraries!
from io import BytesIO, TextIOWrapper
import gzip
import re

BASIC_DIGEST = 'Basic digest'

CVEDA_PSYTOOLS_DATASETS = (
    ('IMGN_ESPAD_PARENT_RC5', BASIC_DIGEST),  # (Drug Use Questionnaire)
)

QUOTED_PATTERN = re.compile(r'".*?"', re.DOTALL)


def main():
    for task, digest in CVEDA_PSYTOOLS_DATASETS:
        digest = digest.upper().replace(' ', '_')
        dataset = 'IMAGEN-{task}-{digest}.csv'.format(task=task, digest=digest)
        logging.info('downloading: {0}'.format(dataset))
        url = BASE_URL + dataset + '.gz'
        # let Requests use ~/.netrc instead of passing an auth parameter
        #     auth = requests.auth.HTTPBasicAuth('...', '...')
        # no need to expose identifiers in the code!
        r = requests.get(url, verify=CA_BUNDLE)
        compressed_data = BytesIO(r.content)
        with gzip.GzipFile(fileobj=compressed_data) as uncompressed_data:
            # unfold quoted text spanning multiple lines
            uncompressed_data = TextIOWrapper(uncompressed_data)
            data = QUOTED_PATTERN.sub(lambda x: x.group().replace('\n', '/'),
                                      uncompressed_data.read())
            # skip files that have not changed since last update
            psytools_path = os.path.join(PSYTOOLS_PSC1_DIR, dataset)
            if os.path.isfile(psytools_path):
                with open(psytools_path, 'r') as uncompressed_file:
                    if uncompressed_file.read() == data:
                        logging.info('skip unchanged file: {0}'
                                     .format(psytools_path))
                        continue
            # write downloaded data into file
            with open(psytools_path, 'w') as uncompressed_file:
                logging.info('write file: {0}'.format(psytools_path))
                uncompressed_file.write(data)


if __name__ == "__main__":
    main()
