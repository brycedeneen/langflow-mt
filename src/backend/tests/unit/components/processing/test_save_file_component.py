import contextlib
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from lfx.components.files_and_knowledge.save_file import SaveToFileComponent
from lfx.schema import Data, DataFrame, Message

from tests.base import ComponentTestBaseWithoutClient


class TestSaveToFileComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture(scope="class", autouse=True)
    def cleanup_test_files(self):
        """Clean up test files after all tests in the class complete."""
        yield
        # Clean up test files created during tests
        test_files = ["test_data.json", "test_message.txt", "test_output.csv"]
        for filename in test_files:
            filepath = Path(filename)
            if filepath.exists():
                with contextlib.suppress(Exception):
                    filepath.unlink()

    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return SaveToFileComponent

    @pytest.fixture
    def default_kwargs(self):
        """Return the default kwargs for the component."""
        sample_df = DataFrame([{"col1": 1, "col2": "a"}, {"col1": 2, "col2": "b"}])
        return {"input": sample_df, "file_name": "test_output", "file_format": "csv"}

    @pytest.fixture
    def file_names_mapping(self):
        """Return the file names mapping for different versions."""
        return []  # New component

    def test_basic_setup(self, component_class, default_kwargs):
        """Test basic component initialization."""
        component = component_class()
        component.set_attributes(default_kwargs)
        assert component.file_name == "test_output"
        assert component.file_format == "csv"

    def test_get_input_type_dataframe(self, component_class):
        """Test input type detection for DataFrame."""
        component = component_class()
        df = DataFrame([{"a": 1}])
        component.set_attributes({"input": df, "file_name": "test", "file_format": "csv"})
        assert component._get_input_type() == "DataFrame"

    def test_get_input_type_data(self, component_class):
        """Test input type detection for Data."""
        component = component_class()
        data = Data(data={"a": 1})
        component.set_attributes({"input": data, "file_name": "test", "file_format": "json"})
        assert component._get_input_type() == "Data"

    def test_get_input_type_message(self, component_class):
        """Test input type detection for Message."""
        component = component_class()
        message = Message(text="test")
        component.set_attributes({"input": message, "file_name": "test", "file_format": "txt"})
        assert component._get_input_type() == "Message"

    def test_get_default_format_dataframe(self, component_class):
        """Test default format for DataFrame is csv."""
        component = component_class()
        df = DataFrame([{"a": 1}])
        component.set_attributes({"input": df, "file_name": "test", "file_format": ""})
        assert component._get_default_format() == "csv"

    def test_get_default_format_data(self, component_class):
        """Test default format for Data is json."""
        component = component_class()
        data = Data(data={"a": 1})
        component.set_attributes({"input": data, "file_name": "test", "file_format": ""})
        assert component._get_default_format() == "json"

    def test_get_default_format_message(self, component_class):
        """Test default format for Message is json."""
        component = component_class()
        message = Message(text="test")
        component.set_attributes({"input": message, "file_name": "test", "file_format": ""})
        assert component._get_default_format() == "json"

    @pytest.mark.asyncio
    async def test_save_dataframe_to_csv(self, component_class):
        """Test saving DataFrame to CSV format - only mock upload."""
        component = component_class(_user_id=str(uuid4()))
        df = DataFrame([{"col1": 1, "col2": "a"}, {"col1": 2, "col2": "b"}])
        component.set_attributes(
            {"input": df, "file_name": "test_output", "local_format": "csv", "storage_location": [{"name": "Local"}]}
        )

        # Mock only the database and upload functions - let file operations run normally
        with (
            patch("langflow.api.v2.files.upload_user_file", new_callable=AsyncMock) as mock_upload,
            patch("lfx.services.deps.session_scope") as mock_session,
            patch(
                "langflow.services.database.models.user.crud.get_user_by_id", new_callable=AsyncMock
            ) as mock_get_user,
        ):
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db
            mock_get_user.return_value = MagicMock()
            mock_upload.return_value = "test_output.csv"

            # Execute - real temp file creation, real DataFrame.to_csv(), real cleanup
            result = await component.save_to_file()

            # Verify
            assert "saved successfully" in result.text
            assert "test_output.csv" in result.text

            # Verify upload was called with a real file
            mock_upload.assert_called_once()
            upload_file = mock_upload.call_args[1]["file"]
            assert upload_file.filename == "test_output.csv"

    @pytest.mark.asyncio
    async def test_save_data_to_json(self, component_class):
        """Test saving Data to JSON format - only mock upload."""
        component = component_class(_user_id=str(uuid4()))
        data = Data(data={"col1": "value1", "col2": "value2"})
        component.set_attributes(
            {"input": data, "file_name": "test_data", "local_format": "json", "storage_location": [{"name": "Local"}]}
        )

        # Mock only the database and upload functions - let file operations run normally
        with (
            patch("langflow.api.v2.files.upload_user_file", new_callable=AsyncMock) as mock_upload,
            patch("lfx.services.deps.session_scope") as mock_session,
            patch(
                "langflow.services.database.models.user.crud.get_user_by_id", new_callable=AsyncMock
            ) as mock_get_user,
        ):
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db
            mock_get_user.return_value = MagicMock()
            mock_upload.return_value = "test_data.json"

            result = await component.save_to_file()

            assert "saved successfully" in result.text
            assert "test_data.json" in result.text

    @pytest.mark.asyncio
    async def test_save_message_to_txt(self, component_class):
        """Test saving Message to txt format - only mock upload."""
        component = component_class(_user_id=str(uuid4()))
        message = Message(text="This is a test message")
        component.set_attributes(
            {
                "input": message,
                "file_name": "test_message",
                "local_format": "txt",
                "storage_location": [{"name": "Local"}],
            }
        )

        # Mock only the database and upload functions - let file operations run normally
        with (
            patch("langflow.api.v2.files.upload_user_file", new_callable=AsyncMock) as mock_upload,
            patch("lfx.services.deps.session_scope") as mock_session,
            patch(
                "langflow.services.database.models.user.crud.get_user_by_id", new_callable=AsyncMock
            ) as mock_get_user,
        ):
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db
            mock_get_user.return_value = MagicMock()
            mock_upload.return_value = "test_message.txt"

            result = await component.save_to_file()

            assert "saved successfully" in result.text
            assert "test_message.txt" in result.text

    @pytest.mark.asyncio
    async def test_cleanup_on_error(self, component_class):
        """Test that temp file is cleaned up even when upload fails."""
        component = component_class(_user_id=str(uuid4()))
        df = DataFrame([{"col1": 1}])
        component.set_attributes(
            {"input": df, "file_name": "test_output", "local_format": "csv", "storage_location": [{"name": "Local"}]}
        )

        # Mock database and upload functions - let file operations run normally
        with (
            patch(
                "langflow.api.v2.files.upload_user_file",
                new_callable=AsyncMock,
                side_effect=Exception("Upload failed"),
            ),
            patch("lfx.services.deps.session_scope") as mock_session,
            patch(
                "langflow.services.database.models.user.crud.get_user_by_id", new_callable=AsyncMock
            ) as mock_get_user,
        ):
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db
            mock_get_user.return_value = MagicMock()

            # Capture temp file path before it gets cleaned up
            import tempfile

            temp_dir = Path(tempfile.gettempdir())
            temp_files_before = set(temp_dir.glob("test_output_*.csv"))

            with pytest.raises(Exception, match="Upload failed"):
                await component.save_to_file()

            # Verify temp file was cleaned up
            temp_files_after = set(temp_dir.glob("test_output_*.csv"))
            # New temp files should have been created and cleaned up
            assert temp_files_after == temp_files_before

    @pytest.mark.asyncio
    async def test_invalid_file_format_for_message(self, component_class):
        """Test that invalid file format raises ValueError."""
        component = component_class(_user_id=str(uuid4()))
        message = Message(text="test")
        component.set_attributes(
            {"input": message, "file_name": "test", "local_format": "csv", "storage_location": [{"name": "Local"}]}
        )

        with (
            patch("lfx.services.deps.session_scope") as mock_session,
            patch(
                "langflow.services.database.models.user.crud.get_user_by_id", new_callable=AsyncMock
            ) as mock_get_user,
        ):
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db
            mock_get_user.return_value = MagicMock()  # admin by default

            with pytest.raises(ValueError, match="Invalid file format"):
                await component.save_to_file()

    @pytest.mark.asyncio
    async def test_invalid_file_format_for_dataframe(self, component_class):
        """Test that invalid file format raises ValueError for DataFrame."""
        component = component_class(_user_id=str(uuid4()))
        df = DataFrame([{"a": 1}])
        component.set_attributes(
            {"input": df, "file_name": "test", "local_format": "txt", "storage_location": [{"name": "Local"}]}
        )

        with (
            patch("lfx.services.deps.session_scope") as mock_session,
            patch(
                "langflow.services.database.models.user.crud.get_user_by_id", new_callable=AsyncMock
            ) as mock_get_user,
        ):
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db
            mock_get_user.return_value = MagicMock()  # admin by default

            with pytest.raises(ValueError, match="Invalid file format"):
                await component.save_to_file()

    @pytest.mark.asyncio
    async def test_missing_file_name(self, component_class):
        """Test that missing file name raises ValueError."""
        component = component_class(_user_id=str(uuid4()))
        df = DataFrame([{"a": 1}])
        component.set_attributes(
            {"input": df, "file_name": "", "local_format": "csv", "storage_location": [{"name": "Local"}]}
        )

        with pytest.raises(ValueError, match="File name must be provided"):
            await component.save_to_file()

    @pytest.mark.asyncio
    async def test_file_name_with_extension_stripped(self, component_class):
        """Test that file extension is properly handled when included in file_name."""
        component = component_class(_user_id=str(uuid4()))
        df = DataFrame([{"col1": 1}])
        component.set_attributes(
            {
                "input": df,
                "file_name": "test_output.csv",
                "local_format": "csv",
                "storage_location": [{"name": "Local"}],
            }
        )

        # Mock only the database and upload functions - let file operations run normally
        with (
            patch("langflow.api.v2.files.upload_user_file", new_callable=AsyncMock) as mock_upload,
            patch("lfx.services.deps.session_scope") as mock_session,
            patch(
                "langflow.services.database.models.user.crud.get_user_by_id", new_callable=AsyncMock
            ) as mock_get_user,
        ):
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db
            mock_get_user.return_value = MagicMock()
            mock_upload.return_value = "test_output.csv"

            result = await component.save_to_file()

            # Should only have .csv once, not .csv.csv
            assert "test_output.csv" in result.text
            assert "test_output.csv.csv" not in result.text

    @pytest.mark.asyncio
    async def test_append_mode_txt_file(self, component_class):
        """Test append mode for text files."""
        from tempfile import NamedTemporaryFile

        # Create a temporary file with existing content
        with NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp_file:
            tmp_file.write("Existing content")
            tmp_path = Path(tmp_file.name)

        try:
            component = component_class(_user_id=str(uuid4()))
            component.set_attributes(
                {
                    "input": Message(text="New content"),
                    "file_name": tmp_path.stem,
                    "file_location": str(tmp_path.parent),
                    "local_format": "txt",
                    "storage_location": [{"name": "Local"}],
                    "append_mode": True,
                }
            )

            with (
                patch("langflow.api.v2.files.upload_user_file", new_callable=AsyncMock) as mock_upload,
                patch("lfx.services.deps.session_scope") as mock_session,
                patch(
                    "langflow.services.database.models.user.crud.get_user_by_id", new_callable=AsyncMock
                ) as mock_get_user,
            ):
                mock_db = AsyncMock()
                mock_session.return_value.__aenter__.return_value = mock_db
                mock_get_user.return_value = MagicMock()
                mock_upload.return_value = tmp_path.name

                result = await component.save_to_file()

                assert "appended to" in result.text
                assert tmp_path.read_text(encoding="utf-8") == "Existing content\nNew content"
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    @pytest.mark.asyncio
    async def test_google_drive_credential_parsing_with_control_characters(self, component_class):
        """Test that GCP service account JSON with literal newlines (control characters) can be parsed.

        This tests the fix for the bug where pasted GCP service account JSON fails with:
        'Invalid control character at: line 1 column 183 (char 182)'
        """
        component = component_class(_user_id=str(uuid4()))

        # Simulate a GCP service account JSON with literal newlines in the private_key field.
        # Use a clearly fake, short key to avoid tripping secret scanners while preserving the newline pattern.
        fake_private_key = "-----BEGIN KEY-----\nFAKE\n-----END KEY-----\n"
        service_account_json = (
            f'{{"type": "service_account", "project_id": "test-project-123", "private_key": "{fake_private_key}"}}'
        )

        message = Message(text="test content")
        component.set_attributes(
            {
                "input": message,
                "file_name": "test_gdrive_file",
                "gdrive_format": "txt",
                "storage_location": [{"name": "Google Drive"}],
                "service_account_key": service_account_json,
                "folder_id": "test_folder_id_123",
            }
        )

        # Mock Google Drive dependencies
        with (
            patch("google.oauth2.service_account.Credentials.from_service_account_info") as mock_creds,
            patch("googleapiclient.discovery.build") as mock_build,
        ):
            mock_drive_service = MagicMock()
            mock_build.return_value = mock_drive_service

            # Mock the file upload response
            mock_drive_service.files().create().execute.return_value = {"id": "file123"}

            result = await component.save_to_file()

            # Verify credentials were parsed successfully (should not raise JSONDecodeError)
            mock_creds.assert_called_once()
            creds_dict = mock_creds.call_args[0][0]

            # Verify the parsed credentials have the expected structure
            assert creds_dict["type"] == "service_account"
            assert creds_dict["project_id"] == "test-project-123"
            assert "private_key" in creds_dict
            assert "BEGIN KEY" in creds_dict["private_key"]

            # Verify successful upload message
            assert "successfully uploaded to Google Drive" in result.text
            assert "file123" in result.text

    @pytest.mark.asyncio
    async def test_google_drive_credential_parsing_strategies(self, component_class):
        """Test various GCP credential parsing strategies."""
        component = component_class(_user_id=str(uuid4()))

        test_cases = [
            # Case 1: Normal JSON (should work)
            ('{"type": "service_account", "project_id": "test"}', "Normal JSON"),
            # Case 2: JSON with literal newlines (the bug case)
            ('{"type": "service_account", "private_key": "-----BEGIN\nKEY\n-----END"}', "With control chars"),
            # Case 3: JSON with extra whitespace
            ('  \n{"type": "service_account", "project_id": "test"}  \n', "With whitespace"),
        ]

        for service_account_json, test_name in test_cases:
            message = Message(text="test")
            component.set_attributes(
                {
                    "input": message,
                    "file_name": "test_file",
                    "gdrive_format": "txt",
                    "storage_location": [{"name": "Google Drive"}],
                    "service_account_key": service_account_json,
                    "folder_id": "test_folder",
                }
            )

            with (
                patch("google.oauth2.service_account.Credentials.from_service_account_info") as mock_creds,
                patch("googleapiclient.discovery.build") as mock_build,
            ):
                mock_drive_service = MagicMock()
                mock_build.return_value = mock_drive_service
                mock_drive_service.files().create().execute.return_value = {"id": f"file_{test_name}"}

                # Should not raise JSONDecodeError for any case
                await component.save_to_file()

                # Verify credentials were parsed
                mock_creds.assert_called_once()
                creds_dict = mock_creds.call_args[0][0]
                assert isinstance(creds_dict, dict)
                assert creds_dict["type"] == "service_account"

                mock_creds.reset_mock()

    @pytest.mark.asyncio
    async def test_append_mode_hidden_for_cloud_storage(self, component_class):
        """append_mode is hidden for AWS / Google Drive, visible for Local (admin user)."""
        component = component_class(_user_id=str(uuid4()))

        admin_user = MagicMock()
        admin_user.is_superuser = True
        admin_user.is_platform_admin = False

        with (
            patch("lfx.services.deps.session_scope") as mock_session,
            patch(
                "langflow.services.database.models.user.crud.get_user_by_id", new_callable=AsyncMock
            ) as mock_get_user,
        ):
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db
            mock_get_user.return_value = admin_user

            # Local
            build_config = {
                "storage_location": {"options": []},
                "file_name": {"show": False},
                "append_mode": {"show": False},
                "local_format": {"show": False},
            }
            result = await component.update_build_config(
                build_config, [{"name": "Local"}], "storage_location"
            )
            assert result["append_mode"]["show"] is True
            assert result["file_name"]["show"] is True
            assert result["local_format"]["show"] is True

            # AWS
            build_config = {
                "storage_location": {"options": []},
                "file_name": {"show": False},
                "append_mode": {"show": False},
                "aws_format": {"show": False},
            }
            result = await component.update_build_config(
                build_config, [{"name": "AWS"}], "storage_location"
            )
            assert result["append_mode"]["show"] is False
            assert result["file_name"]["show"] is True
            assert result["aws_format"]["show"] is True

            # Google Drive
            build_config = {
                "storage_location": {"options": []},
                "file_name": {"show": False},
                "append_mode": {"show": False},
                "gdrive_format": {"show": False},
            }
            result = await component.update_build_config(
                build_config, [{"name": "Google Drive"}], "storage_location"
            )
            assert result["append_mode"]["show"] is False
            assert result["file_name"]["show"] is True
            assert result["gdrive_format"]["show"] is True

    @pytest.mark.asyncio
    async def test_update_build_config_filters_local_for_non_admin(self, component_class):
        """Non-admin user: storage_location options exclude Local."""
        component = component_class(_user_id=str(uuid4()))

        non_admin = MagicMock()
        non_admin.is_superuser = False
        non_admin.is_platform_admin = False

        with (
            patch("lfx.services.deps.session_scope") as mock_session,
            patch(
                "langflow.services.database.models.user.crud.get_user_by_id", new_callable=AsyncMock
            ) as mock_get_user,
            patch(
                "lfx.components.files_and_knowledge.save_file.is_astra_cloud_environment",
                return_value=False,
            ),
        ):
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db
            mock_get_user.return_value = non_admin

            build_config = {
                "storage_location": {"options": [], "value": [{"name": "AWS"}]},
                "file_name": {"show": False},
                "append_mode": {"show": False},
                "aws_format": {"show": False},
                "aws_access_key_id": {"show": False, "advanced": True},
                "aws_secret_access_key": {"show": False, "advanced": True},
                "bucket_name": {"show": False, "advanced": True},
                "aws_region": {"show": False, "advanced": True},
                "s3_prefix": {"show": False, "advanced": True},
            }
            result = await component.update_build_config(
                build_config, [{"name": "AWS"}], "storage_location"
            )
            names = [o["name"] for o in result["storage_location"]["options"]]
            assert "Local" not in names
            assert names == ["AWS", "Google Drive"]

    @pytest.mark.asyncio
    async def test_update_build_config_includes_local_for_admin(self, component_class):
        """Admin user: storage_location options include Local."""
        component = component_class(_user_id=str(uuid4()))

        admin_user = MagicMock()
        admin_user.is_superuser = False
        admin_user.is_platform_admin = True  # platform admin path

        with (
            patch("lfx.services.deps.session_scope") as mock_session,
            patch(
                "langflow.services.database.models.user.crud.get_user_by_id", new_callable=AsyncMock
            ) as mock_get_user,
            patch(
                "lfx.components.files_and_knowledge.save_file.is_astra_cloud_environment",
                return_value=False,
            ),
        ):
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db
            mock_get_user.return_value = admin_user

            build_config = {
                "storage_location": {"options": [], "value": [{"name": "Local"}]},
                "file_name": {"show": False},
                "append_mode": {"show": False},
                "local_format": {"show": False},
            }
            result = await component.update_build_config(
                build_config, [{"name": "Local"}], "storage_location"
            )
            names = [o["name"] for o in result["storage_location"]["options"]]
            assert names == ["Local", "AWS", "Google Drive"]

    @pytest.mark.asyncio
    async def test_update_build_config_no_user_id_treats_as_non_admin(self, component_class):
        """If user_id is unset, treat as non-admin (defensive default)."""
        component = component_class()  # no _user_id

        with patch(
            "lfx.components.files_and_knowledge.save_file.is_astra_cloud_environment",
            return_value=False,
        ):
            build_config = {
                "storage_location": {"options": [], "value": [{"name": "AWS"}]},
                "file_name": {"show": False},
                "append_mode": {"show": False},
                "aws_format": {"show": False},
                "aws_access_key_id": {"show": False, "advanced": True},
                "aws_secret_access_key": {"show": False, "advanced": True},
                "bucket_name": {"show": False, "advanced": True},
                "aws_region": {"show": False, "advanced": True},
                "s3_prefix": {"show": False, "advanced": True},
            }
            result = await component.update_build_config(
                build_config, [{"name": "AWS"}], "storage_location"
            )
            names = [o["name"] for o in result["storage_location"]["options"]]
            assert "Local" not in names

    @pytest.mark.asyncio
    async def test_update_build_config_resets_local_value_for_non_admin(self, component_class):
        """Non-admin loading a flow with Local saved: dropdown value is reset to AWS,
        and local-only fields stay hidden so the UI is internally consistent."""
        component = component_class(_user_id=str(uuid4()))

        non_admin = MagicMock()
        non_admin.is_superuser = False
        non_admin.is_platform_admin = False

        with (
            patch("lfx.services.deps.session_scope") as mock_session,
            patch(
                "langflow.services.database.models.user.crud.get_user_by_id", new_callable=AsyncMock
            ) as mock_get_user,
            patch(
                "lfx.components.files_and_knowledge.save_file.is_astra_cloud_environment",
                return_value=False,
            ),
        ):
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db
            mock_get_user.return_value = non_admin

            build_config = {
                "storage_location": {"options": [], "value": [{"name": "Local", "icon": "hard-drive"}]},
                "file_name": {"show": False},
                "append_mode": {"show": False},
                "local_format": {"show": False},
                "aws_format": {"show": False},
                "aws_access_key_id": {"show": False, "advanced": True},
                "aws_secret_access_key": {"show": False, "advanced": True},
                "bucket_name": {"show": False, "advanced": True},
                "aws_region": {"show": False, "advanced": True},
                "s3_prefix": {"show": False, "advanced": True},
            }
            result = await component.update_build_config(
                build_config, [{"name": "Local"}], "storage_location"
            )
            assert result["storage_location"]["value"][0]["name"] == "AWS"
            # Local-only fields hidden because effective selection is now AWS
            assert result["local_format"]["show"] is False
            assert result["append_mode"]["show"] is False
            # AWS fields shown instead
            assert result["aws_format"]["show"] is True

    def test_storage_location_defaults_to_aws(self, component_class):
        """storage_location seed defaults to AWS — non-admin users never see Local in the seed."""
        storage_input = next(i for i in component_class.inputs if i.name == "storage_location")
        assert storage_input.value == [{"name": "AWS", "icon": "Amazon"}]

    def test_storage_location_is_advanced(self, component_class):
        """Test that storage_location is in advanced controls."""
        storage_input = next(i for i in component_class.inputs if i.name == "storage_location")
        assert storage_input.advanced is True

    @pytest.mark.asyncio
    async def test_file_location_visible_only_for_local(self, component_class):
        """file_location is shown when storage_location == Local; hidden otherwise."""
        component = component_class(_user_id=str(uuid4()))

        admin_user = MagicMock()
        admin_user.is_superuser = True
        admin_user.is_platform_admin = False

        with (
            patch("lfx.services.deps.session_scope") as mock_session,
            patch(
                "langflow.services.database.models.user.crud.get_user_by_id", new_callable=AsyncMock
            ) as mock_get_user,
        ):
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db
            mock_get_user.return_value = admin_user

            # Local — file_location visible
            build_config = {
                "storage_location": {"options": [], "value": [{"name": "Local"}]},
                "file_name": {"show": False},
                "file_location": {"show": False},
                "append_mode": {"show": False},
                "local_format": {"show": False},
            }
            result = await component.update_build_config(
                build_config, [{"name": "Local"}], "storage_location"
            )
            assert result["file_location"]["show"] is True

            # AWS — file_location hidden
            build_config = {
                "storage_location": {"options": [], "value": [{"name": "AWS"}]},
                "file_name": {"show": False},
                "file_location": {"show": False},
                "append_mode": {"show": False},
                "aws_format": {"show": False},
                "aws_access_key_id": {"show": False, "advanced": True},
                "aws_secret_access_key": {"show": False, "advanced": True},
                "bucket_name": {"show": False, "advanced": True},
                "aws_region": {"show": False, "advanced": True},
                "s3_prefix": {"show": False, "advanced": True},
            }
            result = await component.update_build_config(
                build_config, [{"name": "AWS"}], "storage_location"
            )
            assert result["file_location"]["show"] is False

    def test_file_location_input_exists(self, component_class):
        """file_location StrInput is registered on the component."""
        names = [i.name for i in component_class.inputs]
        assert "file_location" in names
        file_location = next(i for i in component_class.inputs if i.name == "file_location")
        assert file_location.required is False
        assert file_location.show is False

    @pytest.mark.asyncio
    async def test_save_to_local_uses_file_location(self, component_class, tmp_path):
        """Explicit file_location places the file in that directory."""
        component = component_class(_user_id=str(uuid4()))
        df = DataFrame([{"col1": 1}])
        component.set_attributes(
            {
                "input": df,
                "file_name": "out",
                "file_location": str(tmp_path),
                "local_format": "csv",
                "storage_location": [{"name": "Local"}],
            }
        )

        with (
            patch("langflow.api.v2.files.upload_user_file", new_callable=AsyncMock) as mock_upload,
            patch("lfx.services.deps.session_scope") as mock_session,
            patch(
                "langflow.services.database.models.user.crud.get_user_by_id", new_callable=AsyncMock
            ) as mock_get_user,
        ):
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db
            mock_get_user.return_value = MagicMock()  # admin by default
            mock_upload.return_value = "out.csv"

            result = await component.save_to_file()

            written = tmp_path / "out.csv"
            assert written.exists()
            assert "out.csv" in result.text

    @pytest.mark.asyncio
    async def test_save_to_local_default_location_is_config_outputs(self, component_class, tmp_path):
        """Empty file_location resolves to <config_dir>/outputs/."""
        component = component_class(_user_id=str(uuid4()))
        df = DataFrame([{"col1": 1}])
        component.set_attributes(
            {
                "input": df,
                "file_name": "default_out",
                "file_location": "",
                "local_format": "csv",
                "storage_location": [{"name": "Local"}],
            }
        )

        fake_settings = MagicMock()
        fake_settings.settings.config_dir = str(tmp_path)

        with (
            patch("langflow.api.v2.files.upload_user_file", new_callable=AsyncMock) as mock_upload,
            patch("lfx.services.deps.session_scope") as mock_session,
            patch(
                "langflow.services.database.models.user.crud.get_user_by_id", new_callable=AsyncMock
            ) as mock_get_user,
            patch(
                "lfx.components.files_and_knowledge.save_file.get_settings_service",
                return_value=fake_settings,
            ),
        ):
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db
            mock_get_user.return_value = MagicMock()
            mock_upload.return_value = "default_out.csv"

            await component.save_to_file()

            written = tmp_path / "outputs" / "default_out.csv"
            assert written.exists()

    @pytest.mark.asyncio
    async def test_save_to_local_strips_path_components_from_file_name(self, component_class, tmp_path):
        """file_name with embedded slashes/traversal is reduced to basename."""
        component = component_class(_user_id=str(uuid4()))
        df = DataFrame([{"col1": 1}])
        component.set_attributes(
            {
                "input": df,
                "file_name": "../escape/foo",
                "file_location": str(tmp_path),
                "local_format": "csv",
                "storage_location": [{"name": "Local"}],
            }
        )

        with (
            patch("langflow.api.v2.files.upload_user_file", new_callable=AsyncMock) as mock_upload,
            patch("lfx.services.deps.session_scope") as mock_session,
            patch(
                "langflow.services.database.models.user.crud.get_user_by_id", new_callable=AsyncMock
            ) as mock_get_user,
        ):
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db
            mock_get_user.return_value = MagicMock()
            mock_upload.return_value = "foo.csv"

            await component.save_to_file()

            assert (tmp_path / "foo.csv").exists()
            # No traversal happened — nothing exists at the parent of tmp_path under "escape"
            assert not (tmp_path.parent / "escape" / "foo.csv").exists()

    @pytest.mark.asyncio
    async def test_save_to_file_local_blocked_for_non_admin(self, component_class):
        """Non-admin attempting Local storage at runtime gets ValueError."""
        component = component_class(_user_id=str(uuid4()))
        df = DataFrame([{"col1": 1}])
        component.set_attributes(
            {"input": df, "file_name": "test_output", "local_format": "csv", "storage_location": [{"name": "Local"}]}
        )

        non_admin = MagicMock()
        non_admin.is_superuser = False
        non_admin.is_platform_admin = False

        with (
            patch("lfx.services.deps.session_scope") as mock_session,
            patch(
                "langflow.services.database.models.user.crud.get_user_by_id", new_callable=AsyncMock
            ) as mock_get_user,
        ):
            mock_db = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_db
            mock_get_user.return_value = non_admin

            with pytest.raises(ValueError, match="platform administrators"):
                await component.save_to_file()

    def test_storage_location_options_helper_admin_includes_local(self):
        """Admin sees Local + AWS + Google Drive."""
        from lfx.components.files_and_knowledge.save_file import _get_storage_location_options

        with patch(
            "lfx.components.files_and_knowledge.save_file.is_astra_cloud_environment",
            return_value=False,
        ):
            options = _get_storage_location_options(is_admin=True)
        names = [o["name"] for o in options]
        assert names == ["Local", "AWS", "Google Drive"]

    def test_storage_location_options_helper_non_admin_excludes_local(self):
        """Non-admin sees only AWS + Google Drive."""
        from lfx.components.files_and_knowledge.save_file import _get_storage_location_options

        with patch(
            "lfx.components.files_and_knowledge.save_file.is_astra_cloud_environment",
            return_value=False,
        ):
            options = _get_storage_location_options(is_admin=False)
        names = [o["name"] for o in options]
        assert names == ["AWS", "Google Drive"]

    def test_storage_location_options_helper_astra_admin_excludes_local(self):
        """Astra environment hides Local even for admins."""
        from lfx.components.files_and_knowledge.save_file import _get_storage_location_options

        with patch(
            "lfx.components.files_and_knowledge.save_file.is_astra_cloud_environment",
            return_value=True,
        ):
            options = _get_storage_location_options(is_admin=True)
        names = [o["name"] for o in options]
        assert names == ["AWS", "Google Drive"]
