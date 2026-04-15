def test_component_imports_and_registers():
    from lfx.components.sftp import SFTPCSVUploadComponent

    assert SFTPCSVUploadComponent.display_name == "SFTP CSV Upload"
    assert SFTPCSVUploadComponent.name == "SFTPCSVUpload"
