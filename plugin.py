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


# Faster than pickle (empirically)
def load_birds():
    """Load birds with caching"""
    try:
        with open('cache/birds.json', 'rb') as f:
            birds = json.load(f)
    except:
        birds = list(_load_birds_no_cache())
        with open(ensure_parent_dir('cache/birds.json'), 'wb') as f:
            json.dump(birds, f)
    return birds


def _load_birds_no_cache():
    fetch_ebird_taxa_if_missing()
    with io.open(ebird_taxa_csv_path, encoding='utf8') as f:
        for ebird in unicode_csv_dict_reader(f):
            yield dict(
                ebird=ebird,
                match_tokens=[
                    # Keep this string munging lightweight -- it can noticeably slow down response time very easily
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
        with io.open(ensure_parent_dir(ebird_taxa_csv_path), 'w', encoding='utf8') as f:
            f.write(content.decode('utf8'))


def normalize_token(token):
    # Keep this string munging lightweight -- it can noticeably slow down response time very easily
    return (token
        .lower()
        .replace("'", '')
    )


def results(fields, original_query):

    # Uncomment for debugging
    # _log('fields: %s' % fields)
    # _log('original_query: %s' % original_query)

    # Parse input
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
                ('banding code', bird['ebird']['BANDING_CODES']),
                ('species code', bird['ebird']['SPECIES_CODE']),
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

    return dict(
        title='birds',
        html=html,
        run_args=show_birds,
    )


def run(*birds):
    if birds:
        bird = birds[0]
        preferences = load_preferences()
        # Open from least to most interesting, so that the most interesting browser tab/window is visible by default
        for key, url_f in reversed([
            ('xeno-canto.org', xeno_canto_url),
            ('peterson-field-guide', peterson_field_guide_url),
            ('ebird.org/map', ebird_map_url),
            ('allaboutbirds.org', allaboutbirds_url),
            ('audubon.org', audubon_url),
        ]):
            if preferences[key]:
                os.system('open %s' % pipes.quote(url_f(bird)))


def xeno_canto_url(bird):
    # view=3 - "sonograms" view instead of default "detailed" view
    # order=dt&dir=1 - sort by "date" reverse
    return 'https://www.xeno-canto.org/species/%s?view=3&order=dt&dir=1' % (
        bird['_sciname']
        .replace(" ", '-')
    )


def peterson_field_guide_url(bird):
    return 'https://academy.allaboutbirds.org/peterson-field-guide-to-bird-sounds/?speciesCode=%s' % (
        bird['_species_code']
    )


def ebird_map_url(bird):
    return 'http://ebird.org/map/%s' % (
        bird['_species_code']
    )


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


def title_case(s):
    return ' '.join(word[0].upper() + word[1:] for word in s.split())


def ensure_parent_dir(path):
    mkdir_p(os.path.dirname(path))
    return path


def mkdir_p(dir):
    os.system('mkdir -p %s' % pipes.quote(dir))


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
