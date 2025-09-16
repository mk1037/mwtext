#!/usr/bin/python3

# -*- coding: utf-8 -*-

# Copyright (C) 2025 Marek Momot
#
# This file is part of mwtext
#
# mwtext is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# mwtext is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with mwtext.  If not, see <http://www.gnu.org/licenses/>.

import argparse
import sys
import re
import pprint
import copy
from fractions import Fraction
#from mido import Message, MetaMessage, MidiFile, MidiTrack
import mido

# global patterns
g_patternBeat = r"(_(\{(-?(\d+\s+)?\d+(/\d+)?!?)?\})?)"
g_patternPointer = r"((<|>)(\{(-?(\d+\s+)?\d+(/\d+)?!?)?\})?)"
g_patternAnchor = r"\^\{(\d{2}:){1,2}\d{2}\.\d{3}(;\d+/\d+!?)?\}"

g_labelBeat = "beat"
g_labelPointer = "pointer"
g_labelAnchor = "anchor"

g_defaults = {
  "anchorSignature" : { "A" : 4, "B" : 4 },
  "pointerDistance" : Fraction(0),
  "beatDuration" : Fraction(1)
}

# parsing options
options = \
  argparse.ArgumentParser( \
                           prog='mwtext', \
                           description='Create text and midi control file',
                           epilog='===================================')

options.add_argument('-i', '--input_file', required=True, \
                     help='Input file')

options.add_argument('-o', '--output_file_mid', required=True, \
                     help='Output midi control file')

options.add_argument('-t', '--output_file_txt', required=True, \
                     help='Output text file')

args = options.parse_args()

#########################################################################
#########################################################################
#########################################################################
print("This is text maker for MW21")
print("Input is \"{}\"\nMsh out is \"{}\"\nTxt out is \"{}\"".format(
  args.input_file, args.output_file_mid, args.output_file_txt ))

#########################################################################
#########################################################################
#########################################################################
# Classes

class LineTokens:
  def __init__(self, p_rawtokens):
    self.tokens = []
    self.isHint = False
    self.comment = ""



#########################################################################
#########################################################################
#########################################################################
# Data structs

rawlines = []



#########################################################################
#########################################################################
#########################################################################


def printSep(title):
  print("{:=^50s}".format(title) )

def readInput(p_file):
  with open(p_file) as l_file:
    lines = l_file.readlines()
  return lines


# This function removes comment and trims whitespaces from content too
def separateComments(p_lines):
  result = []
  linenum = 1
  for i in range(len(p_lines)):
    cline = p_lines[i].strip()
    commentText = ""
    comment = re.search(r'\s*;;.*$', cline)
    if comment:
      commentText = comment.group()
    result.append([cline[:len(cline) - len(commentText)].strip(), commentText.strip(), linenum ])
    linenum += 1
  return result


def splitLineByTokens(p_line):
  if len(p_line) == 0:
    return [""]
  if p_line[0] == '|':
    print("CRITICAL: Line '{}' begins with '|' Exiting ...".format(p_line))
    quit(1)
  splitPoints = []
  for i in range(len(p_line)):
    if p_line[i] == "|":
      splitPoints.append(i)
  spcopy = copy.deepcopy(splitPoints)
  for i in spcopy:
    if i > 0 and p_line[i-1] == '\\':
      splitPoints.remove(i)

  if len(splitPoints)  > 0:
    if splitPoints[-1] == len(p_line) - 1:
      print("CRITICAL: Line '{}' ends with '|' Exiting ...".format(p_line))
      quit(1)

  p_line = p_line + "|"
  splitPoints.append(len(p_line) - 1)

  result = [p_line[0:splitPoints[0]]]

  for i in range(len(splitPoints) - 1):
    result.append(p_line[splitPoints[i]+1:splitPoints[i+1]])

  return result



def splitLines(p_separated):
  result = []
  for cline in p_separated:
    result.append({ "linenum" : cline[2], "rawtokens" : splitLineByTokens(cline[0]), "comment" : cline[1], "hint": False })
  return result


def normalize(p_lines):
  for cline in p_lines:
    if len(cline["rawtokens"][0]) > 0:
      if cline["rawtokens"][0][0] == "~":
        cline["hint"] = True
        cline["rawtokens"][0] = cline["rawtokens"][0][1:]
      cline["rawtokens"][0] = cline["rawtokens"][0].lstrip()
    for i in range(len(cline["rawtokens"])):
      if "" == cline["rawtokens"][i].strip() and len(cline["rawtokens"]) > 1:
        print("CRITICAL: Line nr '{}' is not empty but has empty token. Exiting ...".format(cline["linenum"]))
        quit(1)
      cline["rawtokens"][i] = cline["rawtokens"][i].replace(r"\|", "|")

  return p_lines

def scanPattern(p_line, p_pattern, p_label):
  result = {}
  offset = 0
  t_line = p_line
  while len(t_line) > 0:
    mtch = re.search(p_pattern, t_line)
    if mtch:
      result[mtch.span()[0] + offset] = ((mtch.span()[0] + offset, mtch.span()[1] + offset, p_label, mtch.group()))
      offset += mtch.span()[1]
      t_line = t_line[mtch.span()[1]:]
    else:
      t_line = ""
  return result


def syntaxToken(p_token):
  preresult = {}
  preresult.update( scanPattern(p_token, g_patternBeat, g_labelBeat) )
  preresult.update( scanPattern(p_token, g_patternPointer, g_labelPointer) )
  preresult.update( scanPattern(p_token, g_patternAnchor, g_labelAnchor) )

  return dict(sorted(preresult.items()))

def syntaxRecognize(p_lines):
  for cline in p_lines:
    cline["syntaxTokens"] = []
    for ctoken in cline["rawtokens"]:
      cline["syntaxTokens"].append(syntaxToken(ctoken))
  return p_lines


def semanticMarker(p_markerTuple):
  result = { "atype" : p_markerTuple[2] }
  markerText = p_markerTuple[3]
  updateDefault = False


  if result["atype"] == "beat":
    markerText = markerText[1:] # removing _

    # check if there is {...}
    if len(markerText) > 0:
      markerText = markerText[1:][:-1]
      if len(markerText) > 0:
        if markerText[-1:] == "!":
          updateDefault = True
          markerText = markerText[:-1]
        if len(markerText) > 0:
          result["duration"] = bFraction(markerText)
          if updateDefault:
            g_defaults["beatDuration"] = bFraction(markerText)
        else:
          result["duration"] = g_defaults["beatDuration"]
      else:
        result["duration"] = g_defaults["beatDuration"]
    else:
      result["duration"] = g_defaults["beatDuration"]

  if result["atype"] == "pointer":
    result["direction"] = markerText[0:1]
    markerText = markerText[1:] # removing < or >

    # check if there is {...}
    if len(markerText) > 0:
      markerText = markerText[1:][:-1]
      if len(markerText) > 0:
        if markerText[-1:] == "!":
          updateDefault = True
          markerText = markerText[:-1]
        if len(markerText) > 0:
          result["distance"] = bFraction(markerText)
          if updateDefault:
            g_defaults["pointerDistance"] = bFraction(markerText)
        else:
          result["distance"] = g_defaults["pointerDistance"]
      else:
        result["distance"] = g_defaults["pointerDistance"]
    else:
      result["distance"] = g_defaults["pointerDistance"]

  if result["atype"] == "anchor":
    markerText = markerText[1:] # removing ^
    markerText = markerText[1:][:-1] # removing {   }

    if markerText[-1:] == "!":
      updateDefault = True
      markerText = markerText[:-1]

    chunks = re.split(";", markerText)
    result["span"] = chunks[0]
    result["spanmilis"] = parseSpanMiliseconds(chunks[0])
    if len(chunks) > 1:
      signatureText = re.split("/", chunks[1])
      result["signature"] = { "A" : int(signatureText[0]), "B" : int(signatureText[1]) }
    else:
      result["signature"] = g_defaults["anchorSignature"]

    result["fractionSignature"] = Fraction(int(result["signature"]["A"]), int(result["signature"]["B"]))
    if updateDefault:
      g_defaults["anchorSignature"] = result["signature"]

  return result


def semanticRecognize(p_lines):
  for cline in p_lines:
    semanticTokens = []
    for ctoken in cline["syntaxTokens"]: # ctoken is a dictionary
      semanticToken = []
      for i in sorted(ctoken.keys()):
        semanticToken.append(semanticMarker(ctoken[i]))
      semanticTokens.append(semanticToken)
    cline["semanticTokens"] = semanticTokens
  return p_lines

def getTokenText(p_rawtoken, p_syntaxTokenDict):
  ileft = 0
  iend = len(p_rawtoken)
  result = ""
  for i in sorted(p_syntaxTokenDict.keys()):
    result += p_rawtoken[ileft:p_syntaxTokenDict[i][0]]
    ileft = p_syntaxTokenDict[i][1]
  result += p_rawtoken[ileft:iend]
  return result


def getText(p_lines):
  for cline in p_lines:
    cline["textTokens"] = []
    for i in range(0, len(cline["rawtokens"])):
      cline["textTokens"].append({ "text" : getTokenText(cline["rawtokens"][i], cline["syntaxTokens"][i]), "at" : None, "rt" : None, "offset" : None })
  return p_lines

def enumerateBeats(p_lines):
  i = 0
  cposition = Fraction(0)
  for cline in p_lines:
    for ctoken in cline["semanticTokens"]: # ctoken is a dictionary
      for ctag in ctoken:
        if ctag["atype"] == 'beat':
          ctag["id"] = i
          i += 1
          ctag["abp"] = cposition
          cposition = cposition + ctag["duration"]
  return p_lines

def precheckSemanticTokens(p_lines):
# check if first marker of all is anchor

  wasAnchor = False
  wasBeat = False
  for cline in p_lines:
    for csemtoken in cline["semanticTokens"]:
      pointerCount = 0
      for cmarker in csemtoken:
        if cmarker["atype"] == "anchor":
           wasAnchor = True
           if cmarker["spanmilis"] <= 0:
             print("ERROR! Non-positive span in line {}! Exiting ...\n".format(cline["linenum"]))
             quit(1)
        if cmarker["atype"] == "beat":
          wasBeat = True
          if not wasAnchor:
            print("ERROR! Beat encountered but no anchor before in line {}! Exiting ...\n".format(cline["linenum"]))
            quit(1)
        if cmarker["atype"] == "pointer":
          if not wasBeat:
            print("ERROR! Pointer encountered but no beat before in line {}! Exiting ...\n".format(cline["linenum"]))
            quit(1)
          pointerCount = pointerCount + 1
          if pointerCount > 1:
            print("ERROR! Two pointers in one token in line {}! Exiting ...\n".format(cline["linenum"]))
            quit(1)



def buildSpans(p_lines):
  result = []
  for cline in p_lines:
    for csemtoken in cline["semanticTokens"]:
      for cmarker in csemtoken:
        if cmarker["atype"] == "anchor":
          span = {}
          result.append(span)
          span["span"] = cmarker["span"]
          span["spanmilis"] = cmarker["spanmilis"]
          span["beats"] = Fraction(0)
          span["barsNumber"] = Fraction(0)
          span["signature"] = cmarker["signature"]
          span["fractionSignature"] = cmarker["fractionSignature"]
        if cmarker["atype"] == "beat":
          span["beats"] = span["beats"] + cmarker["duration"]
          span["barsNumber"] = span["beats"] / span["fractionSignature"]
  return result

def checkSpans(p_spans):
  pprint.pprint(p_spans)

  totalFraction = Fraction(0)
  totalMilis = 0

  for span in p_spans:
    if not span["barsNumber"].is_integer():
      print("ERROR! Non-whole bars number in span of length {} ! Exiting ...\n".format(span["span"]))
      quit(1)
    if span["barsNumber"] <= Fraction(0):
      print("ERROR! Zero-length span detected in span of length {} ! Exiting ...\n".format(span["span"])	)
      quit(1)

  for span in p_spans:
    totalFraction = totalFraction + span["beats"]
    totalMilis = totalMilis + span["spanmilis"]

  return (totalFraction, totalMilis)


def calculatePointers(p_lines):
  lastId = None
  lastPosition = Fraction(0)
  nextPosition = Fraction(0)
  for cline in p_lines:
    i = 0
    for csemtoken in cline["semanticTokens"]:
      for ctag in csemtoken:
        if ctag["atype"] == 'beat':
          lastId = ctag["id"]
          lastPosition = nextPosition
          nextPosition = lastPosition + ctag["duration"]
        if ctag["atype"] == 'pointer':
          if ctag["direction"] != ">":
            cline["textTokens"][i]["rt"] = lastId
            cline["textTokens"][i]["offset"] = ctag["distance"]
            cline["textTokens"][i]["at"] = lastPosition + ctag["distance"]
          else:
            cline["textTokens"][i]["rt"] = lastId + 1
            cline["textTokens"][i]["offset"] = ctag["distance"]
            cline["textTokens"][i]["at"] = nextPosition + Fraction(-1) * ctag["distance"]
      i = i + 1
  return p_lines


def checkPointersCrossings(p_lines, p_totalF):
  recentAt = Fraction(0)
  for cline in p_lines:
    for texttoken in cline["textTokens"]:
      if texttoken["at"] is None:
        if texttoken["text"].strip() != "":
          print("WARNING! Missing pointer for non-empty texttoken in line number {}\n".format(cline["linenum"]))
        continue
      if texttoken["at"] < Fraction(0):
        print("ERROR! Negative 'at' for texttoken in line number {} ! Exiting ...\n".format(cline["linenum"]))
        quit(1)
      if texttoken["at"] >= p_totalF:
        print("ERROR! The 'at' for texttoken exceeds total fraction in line number {} ! Exiting ...\n".format(cline["linenum"]))
        quit(1)
      if texttoken["at"] <= recentAt:
        print("ERROR! The 'at' for texttoken crosses or collides previous one in line number {} ! Exiting ...\n".format(cline["linenum"]))
        quit(1)
      recentAt = texttoken["at"]
      if texttoken["at"] is not None and texttoken["text"].strip() == "":
        print("WARNING! Empty texttoken included in line number {} ! Can be intentional\n".format(cline["linenum"]))

def renderMidi(p_spans, p_lines, p_res, p_totalF):
  mid = mido.MidiFile(ticks_per_beat=p_res)
  metaTrack = mido.MidiTrack()
  pointerTrack = mido.MidiTrack()

  recentMetaPos = 0
  recentSignature = None
  recentTempo = None
  for span in p_spans:
    spanTickLen = int((span["beats"] / Fraction(1, 4)) * p_res)
    spanTempo = 1000*span["spanmilis"] // int(span["beats"] / Fraction(1, 4))
    if span["signature"] != recentSignature:
      metaTrack.append(mido.MetaMessage('time_signature', numerator=span["signature"]["A"], denominator=span["signature"]["B"], time=recentMetaPos))
      recentSignature = span["signature"]
      recentMetaPos = 0
    if spanTempo != recentTempo:
      metaTrack.append(mido.MetaMessage('set_tempo', tempo=spanTempo, time=recentMetaPos))
      recentTempo = spanTempo

    recentMetaPos = spanTickLen

  recentAbs = 0

  for cline in p_lines:
    for texttoken in cline["textTokens"]:
      if texttoken["at"] is not None:
        absTick = int((texttoken["at"] / Fraction(1, 4)) * p_res)
        pointerTrack.append(mido.Message('note_on', note=1, velocity=1, channel=3, time=(absTick-recentAbs)))
        pointerTrack.append(mido.Message('note_off', note=1, velocity=0, channel=3, time=10 ))
        recentAbs = absTick+10


  sumTrack = mido.merge_tracks([metaTrack, pointerTrack])
  mid.tracks.append(sumTrack)
  mid.save(args.output_file_mid)

def renderText(p_lines):
  with open(args.output_file_txt, 'w') as f:
#    f.write('A new line.\n')
    for cline in p_lines:
      if cline["rawtokens"] == ['']:
        f.write("\n");
        continue
      result = ""
      for texttoken in cline["textTokens"]:
        if texttoken["at"] is not None and texttoken["text"].strip() != "":
          if result == "":
            result = texttoken["text"]
          else:
            result = result + "|" + texttoken["text"]

      if cline["hint"] and result != "":
        result = '~' + result
      f.write(result + "\n")



def bFraction(p_str):
  #print("Constructing fraction from {0}".format(p_str))
  isNegative = re.compile("^-.*")
  negative = False
  hasSpace = re.compile(r".*\s+ .*")
  if(p_str == ""):
    return Fraction(0)
  source_str = p_str
  if(isNegative.match(source_str)):
    negative = True
    source_str = source_str[1:]
  if(hasSpace.match(source_str)):
    parts = re.split(" +", source_str)
    result = Fraction(parts[0]) + Fraction(parts[1])
  else:
    result = Fraction(source_str)
  if negative:
    return -1 * result
  return result


def parseSpanMiliseconds(p_str):
  result = 0
  chunks = p_str.split(":")

  if len(chunks) > 2:
    if int(chunks[0]) >= 60:
      print("Invalid hours number {}. Exiting ...".format(int(chunks[0])))
      quit(1)

    result = result + int(chunks[0]) * 60 * 60 * 1000
    chunks = chunks[1:]

  if int(chunks[0]) >= 60:
    print("Invalid minutes number {}. Exiting ...".format(int(chunks[0])))
    quit(1)

  result = result + int(chunks[0]) * 60 * 1000
  chunks2 = chunks[1].split(".")

  if int(chunks2[0]) >= 60:
    print("Invalid seconds number {}. Exiting ...".format(int(chunks2[0])))
    quit(1)
  if int(chunks2[1]) >= 1000:
    print("Invalid miliseconds number {}. Exiting ...".format(int(chunks2[1])))
    quit(1)


  result = result + int(chunks2[0]) * 1000 + int(chunks2[1])

  return result






#########################################################################
#########################################################################
#########################################################################



#########################################################################
#########################################################################
#########################################################################

printSep("inputlines")
inputlines = readInput(args.input_file)
#pprint.pprint(inputlines)

printSep("separated")
separated = separateComments(inputlines)
#pprint.pprint(separated)

printSep("splitted")
splitted = splitLines(separated)
#pprint.pprint(splitted)


printSep("normalized")
normalized = normalize(splitted)
#pprint.pprint(normalized)


printSep("syntaxRecognized")
syntaxRecognized = syntaxRecognize(normalized)
#pprint.pprint(syntaxRecognized)


printSep("calculateText")
tokensText = getText(syntaxRecognized)
#pprint.pprint(tokensText)


printSep("semanticTokens")
semanticRecognized = semanticRecognize(tokensText)
#pprint.pprint(semanticRecognized)

printSep("enumeratedBeats")
enumeratedBeats = enumerateBeats(semanticRecognized)
#pprint.pprint(enumeratedBeats)


printSep("precheckSemanticTokens")
precheckSemanticTokens(enumeratedBeats)

printSep("buildSpans")
spans = buildSpans(enumeratedBeats)
#pprint.pprint(spans)

printSep("checkSpans")
(totalF, totalM) = checkSpans(spans)
print("Total miliseconds: {} = {:02d}:{:02d}:{:02d}.{:03d}".format(totalM, (totalM // (60*60*1000) ) % 60, (totalM // (60*1000) ) % 60, (totalM // 1000) % 60, totalM % 1000 ))
print("Total fraction: {}".format(totalF))

printSep("calculatedPointers")
calculatedPointers = calculatePointers(enumeratedBeats)
pprint.pprint(calculatedPointers)


printSep("checkPointersCrossings")
checkPointersCrossings(calculatedPointers, totalF)
#pprint.pprint(calculatedPointers)

printSep("renderMidi")
renderMidi(spans, enumeratedBeats, 384, totalF)

printSep("renderText")
renderText(enumeratedBeats)

