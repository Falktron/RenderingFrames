import json, gzip, struct, boto3, math, sys


# ##### BEGIN GPL LICENSE BLOCK #####
#
#  Extract from Blender's script library included in scripts/modules.
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
# ##### END GPL LICENSE BLOCK #####
def read_blend_rend_chunk(file):
    blendfile = open(file, "rb")

    head = blendfile.read(7)

    if head[0:2] == b'\x1f\x8b':  # gzip magic
        blendfile.seek(0)
        blendfile = gzip.open(blendfile, "rb")
        head = blendfile.read(7)

    if head != b'BLENDER':
        print("not a blend file:", file)
        blendfile.close()
        return []

    is_64_bit = (blendfile.read(1) == b'-')

    # true for PPC, false for X86
    is_big_endian = (blendfile.read(1) == b'V')

    # Now read the bhead chunk!!!
    blendfile.read(3)  # skip the version

    scenes = []

    sizeof_bhead = 24 if is_64_bit else 20

    while blendfile.read(4) == b'REND':
        sizeof_bhead_left = sizeof_bhead - 4

        struct.unpack('>i' if is_big_endian else '<i', blendfile.read(4))[0]
        sizeof_bhead_left -= 4

        # We don't care about the rest of the bhead struct
        blendfile.read(sizeof_bhead_left)

        # Now we want the scene name, start and end frame. this is 32bites long
        start_frame, end_frame = struct.unpack('>2i' if is_big_endian else '<2i', blendfile.read(8))

        scene_name = blendfile.read(64)

        scene_name = scene_name[:scene_name.index(b'\0')]

        try:
            scene_name = str(scene_name, "utf8")
        except TypeError:
            pass

        scenes.append((start_frame, end_frame, scene_name))

    blendfile.close()

    return scenes


def get_number_of_frames(file):
    """Reads the header of the blend file and calculates
    the number of frames it has.

    Keyword arguments:
    file -- Blender file to analyse
    """

    try:
        frame_start, frame_end, scene = read_blend_rend_chunk(file)[0]
    except FileNotFoundError as e:
        print(e.args[1])
        sys.exit(2)
    else:
        return int(frame_end - frame_start + 1)


def download_blender_file_from_s3(uri):
    """Downloads the blend file from S3 and stores it locally.

    Keyword arguments:
    uri -- S3 URI of the file to download
    """

    uri_components = uri.split('s3://')[1].split('/')
    bucket = uri_components[0]
    file = uri_components[1]

    s3 = boto3.resource('s3')
    s3.meta.client.download_file(bucket, file, '/tmp/{}'.format(file))

    return '/tmp/{}'.format(file)



def download_blender_texture_from_s3(uri):
    """Downloads the blend texture and stores it locally.

    Keyword arguments:
    uri -- S3 URI of the file to download
    """

    uri_components = uri.split('s3://')[1].split('/')
    bucket = uri_components[0]
    file = "Place_designs_here_Tshirt.psd"

    s3 = boto3.resource('s3')
    s3.meta.client.download_file(bucket, file, '/tmp/{}'.format(file))

    return '/tmp/{}'.format(file)


def calculate_array_job_size(file, frames_per_job):
    """Calculates the size of the job array

    Keyword arguments:
    file -- Blender file to analyse
    frames_per_job -- Number of frames each Batch job has to render
    """

    # Get the scene's number of frames by reading the header of the blender file
    n_frames = get_number_of_frames(file)

    # Adjust the number of frames per job if needed
    frames_per_job = min(frames_per_job, n_frames)

    # Calculate how many jobs need to be submitted
    return n_frames, math.ceil(n_frames / frames_per_job)


def lambda_handler(event, context):
    # Download the blend file from s3 and save it locally to work with it
    file = download_blender_file_from_s3(event['inputUri'])
    texture = download_blender_texture_from_s3(event['inputUri'])

    # Calculate the size of the array job and extract the number of frames
    n_frames, array_job_size = calculate_array_job_size(file, int(event['framesPerJob']))

    return {
        'statusCode': 200,
        'body': {'arrayJobSize': array_job_size, 'texture': texture}
    }
