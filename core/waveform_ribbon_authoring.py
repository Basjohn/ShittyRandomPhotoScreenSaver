"""Plain authoring contracts for ribbon routing, ribbon cards and colour nodes."""
from __future__ import annotations
import math
from collections.abc import Mapping, Sequence

SOURCES = ('Bass', 'Mids', 'Highs', 'Loudness', 'Onsets', 'Head Wave')
TARGETS = ('height', 'width', 'bend', 'torsion', 'twist', 'stretch', 'lift', 'spread', 'depth',
           'rotation', 'light', 'sparkle', 'colour', 'highlights')


def number(value, low, high):
    if isinstance(value, bool):
        raise ValueError('A finite number is required')
    result = float(value)
    if not math.isfinite(result) or not low <= result <= high:
        raise ValueError(f'Value must be finite in {low}..{high}')
    return result


def admit_routing(value):
    """Every target has six [gain, curve-power] cells. No hidden routing or per-track normalization."""
    if not isinstance(value, Mapping) or set(value) != set(TARGETS):
        raise ValueError('Ribbon routing must contain exactly the declared targets')
    output = {}
    for target in TARGETS:
        row = value[target]
        if len(row) != len(SOURCES) or any(len(cell) != 2 for cell in row):
            raise ValueError('Each ribbon target needs six gain/curve cells')
        output[target] = [[number(gain, 0., 2.), number(power, .25, 4.)] for gain, power in row]
    return output


def route(row, sources, *, passage=1.):
    # Independent gains add; the target's normalized domain is the explicit upper bound.
    # Fast bands articulate inside sustained passage weight. Loudness already IS that weight; admitted
    # events have their own shared passage reward, and Head Wave is an explicitly authored idle source.
    return min(1., sum(gain * max(0., min(1., source)) ** power * (passage if index<3 else 1.)
                       for index,((gain, power), source) in enumerate(zip(row, sources))))


def admit_ribbons(value):
    """Exactly three retained identities; count is a separate faded admission control."""
    if not isinstance(value, Sequence) or len(value) != 3:
        raise ValueError('Three ribbon cards are required')
    result = []
    for card in value:
        if not isinstance(card, Mapping) or set(card) != {'band','height','width','rate','phase','light','quiet','peak'}:
            raise ValueError('Malformed ribbon card')
        if card['band'] not in ('All','Bass','Mids','Highs'):
            raise ValueError('Unknown ribbon band')
        out = {'band': card['band']}
        for key, limits in (('height',(.1,2.)),('width',(.1,2.)),('rate',(.25,2.)),
                            ('phase',(-math.pi*2,math.pi*2)),('light',(0.,4.))):
            out[key] = number(card[key], *limits)
        for key in ('quiet','peak'):
            if len(card[key]) != 2 or any(len(c) != 3 for c in card[key]):
                raise ValueError('Ribbon colours require centre and edge RGB')
            out[key] = [[number(channel,0.,1.) for channel in colour] for colour in card[key]]
        result.append(out)
    return result


def admit_palette(value):
    if not isinstance(value, Mapping) or set(value) != {'low','high'}:
        raise ValueError('A quiet and peak gradient are required')
    result = {}
    positions = set()
    for key in ('low','high'):
        nodes = value[key]
        if not 1 <= len(nodes) <= 6:
            raise ValueError('A gradient needs one to six nodes')
        out = []
        for position, colour in nodes:
            position = number(position,0.,1.)
            if len(colour) != 3 or (out and position <= out[-1][0]):
                raise ValueError('Gradient nodes must be ordered with three colour channels')
            out.append([position,[number(channel,0.,1.) for channel in colour]])
            positions.add(position)
        result[key] = out
    if len(positions) > 6:
        raise ValueError('Quiet and peak gradients may use at most six shared positions')
    return result
