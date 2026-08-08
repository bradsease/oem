import pytest


@pytest.mark.parametrize("file_format", ("kvn", "xml"))
def test_save_as(benchmark, real_oem, tmp_path, file_format):
    """Measure serialization and write I/O for each supported OEM format."""
    output_path = tmp_path / "output.oem"
    benchmark(real_oem.save_as, output_path, file_format=file_format)
