# -*- mode: python; -*-
#
# Copyright (C) 2011 Jonathan Ellis
#
# Author: Jonathan Ellis <jonathan.ellis.research@gmail.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307
# USA
""""""
from __future__ import print_function, division

from StringIO import StringIO
from Bio.Seq import Seq
from Bio import SeqIO

import const
#from const.primer import PrimerDesigner, Primer


class Builder(object):

    """Base primer builder class.

    THIS CLASS SHOULD NOT BE INITALISED DIRECTLY.
    """

    def __init__(self):
        # self.nucleotide_sequence = None
        # self.protein_sequence = None
        self._nseq = None
        self._pseq = None
        #self.mode = 'Restrict'    # Restrict | LIC | Mutate
        self.forward_overhang = ''
        self.reverse_overhang = ''
        self.forward_cloning_seq = ''
        self.reverse_cloning_seq = ''
        self.insert_start_codon = None
        self.insert_stop_codon = None

    def _set_nuc(self, sequence):
        """Set the nucleotide sequence.

        sequence may either be a Bio.Seq object or a string.  If it's a
        string it may have an optional FASTA header.  In all cases it
        will be converted into a Bio.Seq object for storage.
        """
        if isinstance(sequence, basestring):
            sequence = sequence.strip()
            if sequence.startswith('>'):
                record = SeqIO.read(StringIO(sequence), 'fasta')
                sequence = record.seq
            else:
                sequence = Seq(sequence)
        if not isinstance(sequence, Seq):
            raise TypeError(
                'nucleotide sequence is not of type Bio.Seq.Seq: %s' % type(sequence))
        self._nseq = sequence
        self._pseq = sequence.translate()
        if self._pseq[-1] == '*':
            self._pseq = self._pseq[:-1]
            self.has_stop_codon = True
        else:
            self.has_stop_codon = False

    nucleotide_seq = property(lambda self: self._nseq, _set_nuc, None,
        """Nucleotide sequence, stored as Bio.Seq""")

    protein_seq = property(
        lambda self: self._pseq, None, None,
        """The protein sequence, as Bio.Seq type.  This is always just a
        translation of the nucleotide sequence.""")

    def design(self, **kwds):
        """Return a list of PrimerPairs.

        Returns:
           3-tuple, (forward_primers, reverse_primers, primer_pairs).
           Each item is a list.
        """
        
        fw_primers = []
        rv_primers = []

        has_start = 'ATG' if self.insert_start_codon else ''
        # Reverse compliment of stop codon (UAG)
        has_stop = 'CTA' if self.insert_stop_codon else ''
        for start in self.start_positions:
            fw = const.PrimerDesigner(self.nucleotide_seq, start,
                                      'Forward', **kwds)
            fw_primer = const.Primer(start,
                                     self.forward_overhang,
                                     self.forward_cloning_seq,
                                     has_start,
                                     str(fw))
            fw_primers.append(fw_primer)

        for stop in self.stop_positions:
            rv = const.PrimerDesigner(self.nucleotide_seq, stop,
                                      'Reverse', **kwds)
            rv_primer = const.Primer(stop,
                                     self.reverse_overhang,
                                     self.reverse_cloning_seq,
                                     has_stop,
                                     str(rv), reverse=True)
            rv_primers.append(rv_primer)

        constructs = []
        for fw in sorted(fw_primers):
            for rv in sorted(rv_primers):
                p = self.protein_seq[fw.position - 1:rv.position]
                consts.append(const.Construct(fw, rv, p))

        return constructs


class ConstructBuilder(Builder):

    def __init__(self):
        Builder.__init__(self)
        self.mode = 'Restrict'    # Restrict | LIC
        self._start_positions = set()
        self._stop_positions = set()
        
    def add_start_position(self, position):
        self._start_positions.add(position)

    def remove_start_position(self, position=None):
        if position is None:
            self._start_positions = set()
        else:
            self._start_positions.discard(position)

    def add_stop_position(self, position):
        self._stop_positions.add(position)

    def remove_stop_position(self, position=None):
        if position is None:
            self._stop_positions = set()
        else:
            self._stop_positions.discard(position)

    start_positions = property(lambda self: self._start_positions,
                               None, None, '')

    stop_positions = property(lambda self: self._stop_positions,
                              None, None, '')


class SiteBuilder(Builder):

    """Builder for site-mutagenesis."""

    def __init__(self):
        Builder.__init__(self)
        self.mode = 'Mutate'
        self._mutates = set()

    sites = property(lambda self: self._mutates, None, None, '')
        
    def add_site(self, number, from_res, to_res):
        """Add a mutation site to the sequence.

        >>> pb = SiteBuilder()
        >>> pb.add_site(19, 'R', 'Q')
        >>> pb.sites
        set([(19, 'R', 'Q')])
        >>> pb.add_site(3, 'R', 'A')
        >>> sorted(pb.sites)
        [(3, 'R', 'A'), (19, 'R', 'Q')]
        """
        self._mutates.add((number, from_res, to_res))
        
    def remove_site(self, number=None, from_res=None, to_res=None):
        """Remove a mutation site from the sequence.

        >>> pb = SiteBuilder()
        >>> pb.add_site(3, 'R', 'A')
        >>> pb.sites
        set([(3, 'R', 'A')])
        >>> pb.remove_site(3, 'R', 'A')
        >>> pb.sites
        set([])
        >>> pb.add_site(3, 'R', 'A')
        >>> pb.add_site(5, 'W', 'A')
        >>> pb.sites
        set([(3, 'R', 'A'), (5, 'W', 'A')])
        >>> pb.remove_site()
        >>> pb.sites
        set([])
        """
        if number is None:
            self._mutates = set()
        else:
            self._mutates.discard((number, from_res, to_res))
        
    def _mutate_sequence(self, sequence, number, to, use_default=True):
        """Mutate the nucleotide sequence (returns new sequence).

        >>> pb = SiteBuilder()
        >>> pb.nucleotide_seq = 'atggtagttaaagttggtattaacggtttc'
        >>> str(pb.protein_seq)
        'MVVKVGINGF'
        >>> new_seq = pb._mutate_sequence(pb.nucleotide_seq, 6, 'A')
        >>> new_seq.tostring()
        'atggtagttaaagttgcaattaacggtttc'
        >>> new_seq.translate().tostring()
        'MVVKVAINGF'
        >>> new_seq = pb._mutate_sequence(new_seq, 4, 'P')
        >>> new_seq.tostring()
        'atggtagttccagttgcaattaacggtttc'
        >>> new_seq.translate().tostring()
        'MVVPVAINGF'
        """
        # This is E. coli codon usage table (from Codon Usage Database).
        default_codon_table = dict(
            A='GCA', C='TGC', D='GAT', E='GAA', F='TTC',
            G='GGT', H='CAT', I='ATT', K='AAA', L='CTG',
            M='ATG', N='AAC', P='CCA', Q='CAG', R='CGC',
            S='TCA', T='ACA', V='GTT', W='TGG', Y='TAT')
        try:
            codon = self.codon_table[to]
        except AttributeError:
            codon = default_codon_table[to]

        s = list(sequence)
        i = (number - 1) * 3
        s[i:i+3] = codon
        return Seq(''.join(s).lower())

    def design(self, **kwds):
        """Return a list of PrimerPairs."""
        constructs = []
        fw_primers = []
        rv_primers = []
        for number, from_res, to_res in self._mutates:
            if 'use_default' in kwds:
                new_seq = self._mutate_sequence(
                    self.nucleotide_seq, number, to_res, True)
            else:
                new_seq = self._mutate_sequence(
                    self.nucleotide_seq, number, to_res, False)

            fw = const.PrimerDesigner(new_seq, number, 'Site', **kwds)
            fw_primer = const.Primer(number,
                                     self.forward_overhang,
                                     '',
                                     '',
                                     str(fw))

            rv = fw.primer.reverse_complement()
            rv_primer = const.Primer(number,
                                     self.reverse_overhang,
                                     '',
                                     '',
                                     str(rv),
                                     reverse=True)

            fw_primers.append(fw_primer)
            rv_primers.append(rv_primer)
            p = str(new_seq.translate())
            constructs.append(const.Construct(fw_primer, rv_primer, p))

        return constructs
