"""
Bird species names, scientific names, banding codes. Open popular reference sites on <enter>.

Docs:
- https://github.com/nate-parrott/Flashlight/wiki/Creating-a-Plugin
- https://github.com/nate-parrott/Flashlight/wiki/Settings-API
"""

from __future__ import unicode_literals

from collections import OrderedDict
import csv
import io
import json
import os
import os.path
import pipes
import string
import sys
import urllib2

ebird_taxa_csv_path = 'data/ebird-ws1.1-taxa.csv'


def load_preferences():
    with open('preferences.json') as f:
        return json.load(f)


def normalize_token(token):
    return (token
        .lower()
        .translate({ord(c): None for c in string.punctuation})
    )


def load_birds():
    fetch_ebird_taxa_if_missing()
    with io.open(ebird_taxa_csv_path, encoding='utf8') as f:
        for ebird in unicode_csv_dict_reader(f):
            yield dict(
                ebird=ebird,
                match_tokens=[
                    # Normalize once across a concatenated token, for performance
                    normalize_token(' '.join([
                        ebird['COMMON_NAME'],  # e.g. "Wilson's Warbler"
                        ebird['SCIENTIFIC_NAME'],  # e.g. 'Cardellina pusilla'
                        ebird['BANDING_CODES'],  # e.g. 'WIWA'
                        ebird['SPECIES_CODE'],  # e.g. 'wlswar'
                    ])),
                ],
            )


def fetch_ebird_taxa_if_missing():
    if not os.path.exists(ebird_taxa_csv_path):
        content = urllib2.urlopen('http://ebird.org/ws1.1/ref/taxa/ebird?cat=species&fmt=csv').read()
        os.system('mkdir -p %s' % pipes.quote(os.path.dirname(ebird_taxa_csv_path)))
        with io.open(ebird_taxa_csv_path, 'w', encoding='utf8') as f:
            f.write(content.decode('utf8'))


def results(fields, original_query):

    # _log('fields: %s' % fields)
    # _log('original_query: %s' % original_query)

    query = fields['~query']

    # Load data
    birds = load_birds()

    # Filter birds to ones that match tokens from `query`
    query_tokens = normalize_token(query).split()
    matched_birds = []
    for bird in birds:
        if all(
            any(
                query_token in match_token  # Substring
                for match_token in bird['match_tokens']
            )
            for query_token in query_tokens
        ):
            matched_birds.append(bird)

    # Make prettier bird dicts to present to the user (as an html table, below)
    #   - Input schema: sp, commonname, sciname, spec, conf, spec6, conf6
    show_birds = sorted(
        [
            OrderedDict([
                ('name', bird['ebird']['COMMON_NAME']),
                ('code', bird['ebird']['BANDING_CODES']),
                ('sciname', bird['ebird']['SCIENTIFIC_NAME']),
                # Not for display
                ('_commonname', bird['ebird']['COMMON_NAME']),
                ('_sciname', bird['ebird']['SCIENTIFIC_NAME']),
                ('_banding_codes', bird['ebird']['BANDING_CODES']),
                ('_species_code', bird['ebird']['SPECIES_CODE']),
            ])
            for bird in matched_birds
        ],
        key=lambda bird: bird['name'],
    )
    items_for_display = lambda d: [(k, v) for k, v in d.items() if not k.startswith('_')]

    # Output html, from show_birds
    first_show_bird = show_birds[0] if show_birds else {}
    html = '''
        <style type="text/css">
            table, td, th {
                border: 0px solid gray;
                white-space: nowrap;
            }
            table {
                border-collapse: collapse;
            }
            td, th {
                padding: 3px;
            }
            th {
                text-align: left;
            }
            .footer, .footer a {
                margin-top: 3ex;
                color: lightgray;
                text-align: center;
            }
        </style>
        <table>
            %(trs)s
        </table>
        <div class="footer">
            (Data from
            <a href="https://confluence.cornell.edu/display/CLOISAPI/eBird-1.1-SpeciesReference">ebird.org</a>)
        </div>
    ''' % dict(
        trs=''.join(
            '<tr>%s</tr>\n' % tr
            for tr in (
                # Heading row [nah, omit since it's pretty self explanatory]
                # [''.join('<th>%s</th>\n' % k for k, v in items_for_display(first_show_bird))] +
                # Bird rows
                [''.join('<td>%s</td>\n' % v for k, v in items_for_display(bird)) for bird in show_birds]
            )
        ),
    )

    return {
        'run_args': show_birds,
        'title': 'bird search',
        'html': html,
    }


def run(*birds):
    if birds:
        bird = birds[0]
        preferences = load_preferences()
        if preferences['audubon.org']:
            os.system('open %s' % pipes.quote(audubon_url(bird)))
        if preferences['allaboutbirds.org']:
            os.system('open %s' % pipes.quote(allaboutbirds_url(bird)))
        if preferences['ebird.org/map']:
            os.system('open %s' % pipes.quote(ebird_map_url(bird)))
        if preferences['xeno-canto.org']:
            os.system('open %s' % pipes.quote(xeno_canto_url(bird)))


def allaboutbirds_url(bird):
    return 'https://www.allaboutbirds.org/guide/%s' % (
        title_case(bird['_commonname'])
        .replace("'", '')
        .replace(" ", '_')
    )


def audubon_url(bird):
    return 'http://www.audubon.org/field-guide/bird/%s' % (
        bird['_commonname']
        .lower()
        .replace("'", '')
        .replace(" ", '-')
    )


def ebird_map_url(bird):
    return 'http://ebird.org/map/%s' % (
        bird['_species_code']
    )


def xeno_canto_url(bird):
    # view=3 - "sonograms" view instead of default "detailed" view
    return 'https://www.xeno-canto.org/species/%s?view=3' % (
        bird['_sciname']
        .replace(" ", '-')
    )


def title_case(s):
    return ' '.join(word[0].upper() + word[1:] for word in s.split())


# To view logs, use FlashlightTool app (http://flashlighttool.42pag.es/)
def _log(x):
    sys.stderr.write('%s\n' % x)  # Comment out to disable logging


# py2 csv doesn't understand unicode
#   - Based on example at https://docs.python.org/2/library/csv.html
def unicode_csv_reader(unicode_csv_data, **kwargs):
    for row in csv.reader((line.encode('utf8') for line in unicode_csv_data), **kwargs):
        yield [cell.decode('utf8') for cell in row]
def unicode_csv_dict_reader(unicode_csv_data, **kwargs):
    rows = unicode_csv_reader(unicode_csv_data, **kwargs)
    header = next(rows)
    for row in rows:
        yield dict(zip(header, row))
