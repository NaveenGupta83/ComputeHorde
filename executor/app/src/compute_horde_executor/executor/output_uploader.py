from __future__ import annotations

import abc
import pathlib
import tempfile
import zipfile
from typing import Type, Self

import httpx
from django.conf import settings

from compute_horde.em_protocol.miner_requests import UploadOutput, UploadOutputType


class OutputUploader(metaclass=abc.ABCMeta):
    """Upload the output directory to JobRequest.UploadOutput"""
    def __init__(self, upload_output: UploadOutput):
        self.upload_output = upload_output

    @abc.abstractmethod
    async def upload(self, directory: pathlib.Path): ...

    @classmethod
    @abc.abstractmethod
    def handles_output_type(cls) -> UploadOutputType: ...

    __output_type_map: dict[UploadOutputType, Type[OutputUploader]] = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.__output_type_map[cls.handles_output_type()] = cls

    @classmethod
    def for_upload_output(cls, upload_output: UploadOutput) -> Self:
        return cls.__output_type_map[upload_output.upload_type](upload_output)


class ZipAndHTTPPostOutputUploader(OutputUploader):
    """Zip the upload the output directory and HTTP POST the zip file to the given URL"""
    @classmethod
    def handles_output_type(cls) -> UploadOutputType:
        return UploadOutputType.zip_and_http_post

    async def upload(self, directory: pathlib.Path):
        with tempfile.TemporaryFile() as fp:
            zipf = zipfile.ZipFile(fp, mode="w")
            for file in directory.glob('**/*'):
                zipf.write(filename=file, arcname=file.relative_to(directory))

            file_size = fp.tell()
            fp.seek(0)

            if file_size > settings.OUTPUT_ZIP_UPLOAD_MAX_SIZE_BYTES:
                raise Exception('Attempting to upload too large file')

            async with httpx.AsyncClient() as client:
                form_fields = {
                    "Content-Type": "application/zip",
                    **self.upload_output.post_form_fields,
                }
                files = {"file": ("output.zip", fp, "application/zip")}
                headers = {
                    "Content-Length": str(file_size),
                    "Content-Type": "application/zip",
                }
                await client.post(
                    url=self.upload_output.post_url,
                    data=form_fields,
                    files=files,
                    headers=headers,
                )
