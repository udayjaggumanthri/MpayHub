"""MDM sync upstream chunking helpers."""

from django.test import SimpleTestCase

from apps.bbps.catalog.orchestrator import MDM_UPSTREAM_CHUNK_SIZE, _chunks


class MdmChunkHelpersTests(SimpleTestCase):
    def test_chunks_split_large_id_list(self):
        ids = [f'B{i:04d}' for i in range(53)]
        parts = _chunks(ids, MDM_UPSTREAM_CHUNK_SIZE)
        self.assertEqual(len(parts), 3)
        self.assertEqual(len(parts[0]), MDM_UPSTREAM_CHUNK_SIZE)
        self.assertEqual(len(parts[1]), MDM_UPSTREAM_CHUNK_SIZE)
        self.assertEqual(len(parts[2]), 3)
        self.assertEqual([x for part in parts for x in part], ids)
