# encoding: utf-8
import io
import struct
import ctypes
import json
import sys
import traceback
try:
    from collections import OrderedDict
except:
    OrderedDict = dict
    

TIMELINE_SCALE      = 0
TIMELINE_ROTATE     = 1
TIMELINE_TRANSLATE  = 2
TIMELINE_ATTACHMENT = 3
TIMELINE_COLOR      = 4
TIMELINE_FLIPX      = 5
TIMELINE_FLIPY      = 6

CURVE_LINEAR  = 0
CURVE_STEPPED = 1
CURVE_BEZIER  = 2

class AttachmentType(object):
    region = 0
    boundingbox = 1
    mesh = 2
    skinnedmesh = 3


class DataInputStream:
    def __init__(self, filename):
        self.stream = io.BytesIO(open(filename, "rb").read())

    def read(self):
        return ord(self.stream.read(1))

    def readByte(self):
        return self.read()

    def readFloat(self):
        data = self.stream.read(4)
        fval = struct.unpack(">f", data)[0]
        return fval

    def readShort(self):
        data = self.stream.read(2)
        ival = struct.unpack(">h", data)[0]
        return ival

    def readInt(self):
        data = self.stream.read(4)
        ival = struct.unpack(">i", data)[0]
        return ival

    def readUInt(self):
        data = self.stream.read(4)
        ival = struct.unpack(">I", data)[0]
        return ival

    def readBoolean(self):
        return bool(self.read())


class DataInput(DataInputStream):
    def __init__(self, filename):
        DataInputStream.__init__(self, filename)
        self.chars = [""] * 32

    def readColor(self):
        return "%.8x"%self.readUInt()

    def readFloatArray(self, scale = 1.0):
        size = self.readInt(True)

        result = []
        if scale == 1.0:
            for i in range(size):
                result.append(self.readFloat())
        else:
            for i in range(size):
                result.append(self.readFloat() * scale)

        return result

    def readShortArray(self):
        size = self.readInt(True)

        result = []
        for i in range(size):
            result.append(self.readShort())

        return result

    def readIntArray(self):
        size = self.readInt(True)

        result = []
        for i in range(size):
            result.append(self.readInt())

        return result
        
    def readInt(self, optimizePositive = None):
        if optimizePositive is None:
            return DataInputStream.readInt(self)

        b = self.read()
        result = b & 0x7F
        if ((b & 0x80) != 0):
            b = self.read()
            result |= (b & 0x7F) << 7
            if ((b & 0x80) != 0):
                b = self.read()
                result |= (b & 0x7F) << 14
                if ((b & 0x80) != 0):
                    b = self.read()
                    result |= (b & 0x7F) << 21
                    if ((b & 0x80) != 0):
                        b = self.read()
                        result |= (b & 0x7F) << 28
        return ctypes.c_int(result if optimizePositive else (ctypes.c_uint((ctypes.c_uint(result).value >> 1)).value ^ -(result & 1))).value

    def readString(self):
        charCount = self.readInt(True)
        if charCount == 0:
            return None
        elif charCount == 1:
            return ""

        #print "charCount:", charCount
        charCount-= 1
        if len(self.chars) < charCount:
            self.chars = [""] * charCount

        chars = self.chars;
        # Try to read 7 bit ASCII chars.
        charIndex = 0
        b = 0
        while charIndex < charCount:
            b = self.read()
            if b > 127:
                break
            charIndex += 1
            chars[charIndex] = chr(b)
            #print chars, charCount, charIndex

        
        # If a char was not ASCII, finish with slow path.
        if charIndex < charCount:
            self.readUtf8_slow(charCount, charIndex, b)
        return "".join(self.chars[0:charCount + 1])
    
    def readUtf8_slow(self, charCount, charIndex, b):
        chars = self.chars;
        while True:
            brsh4 = b >> 4

            if brsh4 in [0, 1, 2, 3, 4, 5, 6, 7]:
                chars[charIndex] = chr(b)
                break
            elif brsh4 in [12, 13]:
                chars[charIndex] = chr((b & 0x1F) << 6 | self.read() & 0x3F)
                break
            elif brsh4 in [14]:
                chars[charIndex] = chr((b & 0x0F) << 12 | (self.read() & 0x3F) << 6 | self.read() & 0x3F)
                break
                    
            charIndex += 1      
            if charIndex >= charCount:
                break
            b = self.read() & 0xFF

#filename = "/Users/lqefn/Documents/code/spine-runtimes/spine-libgdx/spine-libgdx-tests/assets/spineboy/spineboy.skel"
filename = "/Users/lqefn/Downloads/龟丞相/skeleton.skel"
input = DataInput(filename)

class Object(dict):
    def __getattr__(self, attr):
        try:
            value = self[attr]
        except KeyError:
            raise AttributeError, attr
        return value

    def __setattr__(self, attr, value):
        self[attr] = value

    def __delattr__(self, attr):
        try:
            del self[attr]
        except KeyError:
            raise AttributeError, attr

def readSkeletonData(input, scale):
    skeletonData = Object()
    skeletonData.skeleton = Object()
    skeletonData.skeleton.hash = input.readString()
    skeletonData.skeleton.spine = input.readString()
    skeletonData.skeleton.width = input.readFloat()
    skeletonData.skeleton.height = input.readFloat()

    nonessential = input.readBoolean()
    if nonessential:
        print "nonessential:", nonessential
        skeletonData.imgPath = input.readString()

    bonesCount = input.readInt(True)
    print("bonesCount:", bonesCount)
    skeletonData.bones = []
    for i in range(bonesCount):
        name = input.readString()
        parentIndex = input.readInt(True) - 1
        boneData = Object()
        boneData.name = name
        #boneData.parentIndex = parentIndex
        boneData.parent = skeletonData.bones[parentIndex].name if parentIndex >= 0 else None

        boneData.x = input.readFloat() * scale
        boneData.y = input.readFloat() * scale
        boneData.scaleX = input.readFloat()
        boneData.scaleY = input.readFloat()
        boneData.rotation = input.readFloat()
        boneData.length = input.readFloat() * scale
        boneData.flipX = input.readBoolean()
        boneData.flipY = input.readBoolean()
        boneData.inheritScale = input.readBoolean()
        boneData.inheritRotation = input.readBoolean()
        if nonessential:
            boneData.color = input.readColor()

        skeletonData.bones.append(boneData)

    ikCount = input.readInt(True)
    print("ikCount:", ikCount)
    skeletonData.ik = [None] * ikCount
    for i in range(ikCount):
        print("ik:", i)
        ikData = Object()

        name = input.readString()

        ikData.name = name
        ikData.bones = []
        ikBoneCount = input.readInt(True)
        for ii in range(ikBoneCount):
            boneIndex = input.readInt(True)
            ikData.bones.append(skeletonData.bones[boneIndex].name)

        ikData.target = skeletonData.bones[input.readInt(True)].name
        ikData.mix = input.readFloat()
        ikData.bendDirection = input.readByte()

        skeletonData.ik[i] = ikData

    slotsCount = input.readInt(True)
    print("slotsCount:", slotsCount)
    skeletonData.slots = [None] * slotsCount
    for i in range(slotsCount):
        slotData = Object()

        slotData.name = input.readString()
        boneIndex = input.readInt(True)
        slotData.bone = skeletonData.bones[boneIndex].name
        slotData.color = input.readColor()
        slotData.attachmentName = input.readString()
        slotData.additiveBlending = input.readBoolean()

        skeletonData.slots[i] = slotData

    skeletonData.skins = {}
    defaultSkin = readSkin(input, "default", nonessential, scale)
    if defaultSkin is not None:
        skeletonData.skins["default"] = defaultSkin

    for i in range(input.readInt(True)):
        skinName = input.readString()
        skeletonData.skins[skinName] = readSkin(input, skinName, nonessential, scale)

    eventCount = input.readInt(True)
    print("eventCount:", eventCount)
    skeletonData.events = []
    for i in range(eventCount):
        eventData = Object()
        eventData.name = input.readString()
        eventData.intValue = input.readInt(False)
        eventData.floatValue = input.readFloat()
        eventData.stringValue = input.readString()
        skeletonData.events.append(eventData)

    animationsCount = input.readInt(True)
    print("animationsCount:", animationsCount)
    skeletonData.animations = []
    for i in range(animationsCount):
        animationName = input.readString()
        if not readAnimation(animationName, input, skeletonData, scale):
            break

    return skeletonData

def readSkin(input, name, nonessential, scale):
    slotCount = input.readInt(True)
    if slotCount == 0:
        return None

    skinData = Object()

    for i in range(slotCount):
        slotIndex = input.readInt(True)
        attachmentCount = input.readInt(True)
        for ii in range(attachmentCount):
            attachmentName = input.readString()
            skinData[attachmentName] = {attachmentName: readAttachment(input, skinData, name, nonessential, scale)}
    return skinData
    
def readAttachment(input, skin, attachmentName, nonessential, scale):
    name = input.readString()
    if name is None:
        name = attachmentName

    attachmentType = input.readByte()
    if attachmentType == AttachmentType.region:
        path = input.readString()
        if path is None:
            path = name

        region = Object()
        #region.skin = skin
        region.type = "region"
        region.name = name
        region.path = path
        region.x = input.readFloat() * scale
        region.y = input.readFloat() * scale
        region.scaleX = input.readFloat()
        region.scaleY = input.readFloat()
        region.rotation = input.readFloat()
        region.width = input.readFloat() * scale
        region.height = input.readFloat() * scale 
        region.color = input.readColor()

        return region
    elif attachmentType == AttachmentType.boundingbox:
        box = Object()
        box.type = "boundingbox"

        #box.skin = skin
        box.name = name 
        box.vertices = input.readFloatArray(scale)

        return box

    elif attachmentType == AttachmentType.mesh:
        path = input.readString()
        if path is None:
            path = name

        mesh = Object()
        mesh.type = "mesh"
        #mesh.skin = skin
        mesh.name = name
        mesh.path = path

        mesh.uvs = input.readFloatArray(1.0)
        mesh.triangles = input.readShortArray()
        mesh.vertices = input.readFloatArray(1.0)
        mesh.hullLengh = input.readInt(True)

        if nonessential:
            mesh.edges = input.readIntArray()
            mesh.width = input.readFloat()
            mesh.height = input.readFloat()

        return mesh

    elif attachmentType == AttachmentType.skinnedmesh:
        path = input.readString()
        if path is None:
            path = name

        mesh = Object()
        mesh.type = "skinnedmesh"
        #mesh.skin = skin
        mesh.name = name
        mesh.path = path

        mesh.uvs = input.readFloatArray(1.0)
        mesh.triangles = input.readShortArray()
        mesh.vertices = input.readFloatArray()
        mesh.hull = input.readInt(True)

        if nonessential:
            mesh.edges = input.readIntArray()
            mesh.width = input.readFloat()
            mesh.height = input.readFloat()

        return mesh

    return None

def readAnimation(name, input, skeletonData, scale):
    ok = True
    print("readAnimation:", name)
    timelines = []

    duration = 0

    try:
        # Slot timelines.
        print("Slot timelines.")
        for i in range(input.readInt(True)):
            slotIndex = input.readInt(True)
            for ii in range(input.readInt(True)):
                timelineType = input.readByte()
                frameCount = input.readInt(True)
                if timelineType == TIMELINE_COLOR:
                    timeline = Object()
                    timeline.slotIndex = slotIndex
                    timeline.frames = []
                    timeline.colors = []
                    timeline.curvews = []
                    for frameIndex in range(frameCount):
                        timeline.frames.append(input.readFloat())
                        timeline.colors.append(input.readColor())
                        if frameIndex < frameCount - 1:
                            timeline.curvews.append(readCurve(input))          

                    timelines.append(timeline)

                elif timelineType == TIMELINE_ATTACHMENT:
                    timeline = Object()
                    timeline.slotIndex = slotIndex

                    timeline.frames = []
                    timeline.attachments = []
                    for frameIndex in range(frameCount):
                        timeline.frames.append(input.readFloat())
                        timeline.attachments.append(input.readString())

                    timelines.append(timeline)

        # Bone timelines
        print("Bone timelines")
        for i in range(input.readInt(True)):
            boneIndex = input.readInt(True)
            for ii in range(input.readInt(True)):
                timelineType = input.readByte()
                frameCount = input.readInt(True)
                if timelineType == TIMELINE_ROTATE:
                    timeline = Object()
                    timeline.times = []
                    timeline.angles = []
                    timeline.curvews = []
                    timeline.boneIndex = boneIndex
                    for frameIndex in range(frameCount):
                        timeline.times.append(input.readFloat())
                        timeline.angles.append(input.readFloat())
                        if frameIndex < frameCount - 1:
                            timeline.curvews.append(readCurve(input))   

                    timelines.append(timeline)

                elif timelineType == TIMELINE_TRANSLATE or timelineType == TIMELINE_SCALE:
                    timeline = Object()
                    timeline.times = []
                    timeline.x = []
                    timeline.y = []
                    timeline.curvews = []
                    timeline.boneIndex = boneIndex
                    for frameIndex in range(frameCount):
                        timeline.times.append(input.readFloat())
                        timeline.x.append(input.readFloat())
                        timeline.y.append(input.readFloat())
                        if frameIndex < frameCount - 1:
                            timeline.curvews.append(readCurve(input))   

                    timelines.append(timeline)

                elif timelineType == TIMELINE_FLIPX or timelineType == TIMELINE_FLIPY:
                    timeline = Object()
                    timeline.boneIndex = boneIndex
                    timeline.times = []
                    timeline.flips = []
                    for frameIndex in range(frameCount):
                        timeline.times.append(input.readFloat())
                        timeline.flips.append(input.readFloat())

                    timelines.append(timeline)

        # IK timelines.
        print("IK timelines.")
        for i in range(input.readInt(True)):
            ikIndex = input.readInt(True)
            ikConstraint = skeletonData.ik[ikIndex]
            #print("ik timeline[%d]: " % i, ikConstraint)
            frameCount = input.readInt(True)
            timeline = Object()
            timeline.ikConstraintIndex = ikIndex
            timeline.time = []
            timeline.mix = []
            timeline.bendDirection = []
            timeline.curvews = []
            for frameIndex in range(frameCount):
                timeline.time.append(input.readFloat())
                timeline.mix.append(input.readFloat())
                timeline.bendDirection.append(input.readByte())
                if frameIndex < frameCount - 1:
                    timeline.curvews.append(readCurve(input))   

            timelines.append(timeline)

        # FFD timelines.
        print("FFD timelines.")
        for i in range(input.readInt(True)):
            skinIndex = input.readInt(True)
            skin = skeletonData.skins[skinIndex]
            for ii in range(input.readInt(True)):
                slotIndex = input.readInt(True)
                for iii in range(input.readInt(True)):
                    attachmentName = input.readString()
                    attachment = filter(lambda item: item.name == attachmentName and item.slotIndex == slotIndex, skin.attachments)[0]
                    #print("attachment:", attachment)
                    frameCount = input.readInt(True)
                    timeline = Object()
                    timeline.slotIndex = slotIndex
                    timeline.attachment = attachment
                    timeline.times = []
                    timeline.frameVertices = []
                    timeline.curvews = []
                    for frameIndex in range(frameCount):
                        time = input.readFloat()

                        vertexCount = 0
                        vertices = []
                        if attachment.attachment.type == "mesh":
                            vertexCount = len(attachment.attachment.vertices)
                        else:
                            vertexCount = len(attachment.attachment.vertices) / 3 * 2

                        end = input.readInt(True)
                        if end == 0:
                            if attachment.attachment.type == "mesh":
                                vertices = attachment.attachment.vertices
                            else:
                                vertices = [0.0] * vertexCount
                        else:
                            vertices = [0.0] * vertexCount
                            start = input.readInt(True)
                            end += start
                            for v in range(start, end):
                                vertices[v] = input.readFloat()
                            if attachment.attachment.type == "mesh":
                                meshVertices = attachment.attachment.vertices
                                for v in range(len(vertices)):
                                    vertices[v] = meshVertices[v]
                        timeline.times.append(time)
                        timeline.frameVertices.append(vertices)
                        if frameIndex < frameCount - 1:
                            timeline.curvews.append(readCurve(input))  

                    timelines.append(timeline)

        # Draw order timeline.        
        drawOrderCount = input.readInt(True)
        print("Draw order timeline.", drawOrderCount)
        if drawOrderCount > 0:
            timeline = Object()
            timeline.times = []
            timeline.drawOrder = []
            slotCount = len(skeletonData.slots)
            for i in range(drawOrderCount):
                offsetCount = input.readInt(True)
                drawOrder = [-1] * slotCount
                unchanged = [0] * (slotCount - offsetCount)
                originalIndex = 0
                unchangedIndex = 0;
                for ii in range(offsetCount):
                    slotIndex = input.readInt(True)
                    while originalIndex != slotIndex:
                        unchanged[unchangedIndex] = originalIndex
                        unchangedIndex += 1
                        originalIndex += 1

                    newIndex = originalIndex + input.readInt(True)
                    drawOrder[newIndex] = originalIndex
                    originalIndex += 1
                while originalIndex < slotCount:
                    unchanged[unchangedIndex] = originalIndex
                    unchangedIndex += 1
                    originalIndex += 1
                for ii in range(slotCount - 1, -1, -1):
                    if drawOrder[ii] == -1:
                        unchangedIndex -= 1
                        drawOrder[ii] = unchanged[unchangedIndex]
                timeline.times.append(input.readFloat())
                timeline.drawOrder.append(drawOrder)

            timelines.append(timeline)

        # Event timeline.
        print("Event timeline.")
        eventCount = input.readInt(True)
        if eventCount > 0:
            timeline = Object()
            timeline.times = []
            timeline.events = []
            for i in range(eventCount):
                time = input.readFloat()
                eventData = skeletonData.events[input.readInt(True)]
                event = Object()
                event.eventData = eventData
                event.intValue = input.readInt(False)
                event.floatValue = input.readFloat()

                if input.readBoolean():
                    event.stringValue = input.readString()
                else:
                    eventData.stringValue

                timeline.times.append(time)
                timeline.events.append(event)

            timelines.append(timeline)

    except Exception as e:
        print(e)
        traceback.print_exc(file=sys.stdout)
        ok = False

    skeletonData.animations.append(Object(animationName = name, timelines = timelines))
    return ok


def readCurve(input):
    curveType = input.readByte()
    if curveType == CURVE_STEPPED:
        return "stepped"
    elif curveType == CURVE_BEZIER:
        return (
            input.readFloat(),
            input.readFloat(),
            input.readFloat(),
            input.readFloat(),
        )


print(json.dumps(readSkeletonData(input, 1.0), indent = 4, sort_keys = True))
