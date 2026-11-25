"""Check that the main Windows icon group contains the shipped icon artwork."""
import struct
import sys
from pathlib import Path

import pefile


def ico_images(data):
    count = struct.unpack_from('<H', data, 4)[0]
    images = set()
    for index in range(count):
        length, offset = struct.unpack_from('<II', data, 6 + index * 16 + 8)
        images.add(data[offset:offset + length])
    return images


def executable_images(executable):
    with pefile.PE(str(executable)) as pe:
        resources = {entry.id: entry for entry in pe.DIRECTORY_ENTRY_RESOURCE.entries}

        def read(entry):
            resource = entry.directory.entries[0].data.struct
            return pe.get_data(resource.OffsetToData, resource.Size)

        group = read(resources[pefile.RESOURCE_TYPE['RT_GROUP_ICON']].directory.entries[0])
        icons = {entry.id: read(entry)
                 for entry in resources[pefile.RESOURCE_TYPE['RT_ICON']].directory.entries}
        count = struct.unpack_from('<H', group, 4)[0]
        return {icons[struct.unpack_from('<H', group, 6 + index * 14 + 12)[0]]
                for index in range(count)}


if __name__ == '__main__':
    expected = ico_images(Path(sys.argv[1]).read_bytes())
    actual = executable_images(Path(sys.argv[2]))
    if not expected or expected != actual:
        raise SystemExit('Packaged executable has different icon resources.')
    print(f'Verified all {len(expected)} Chess Engine Battle icon sizes in the executable.')
