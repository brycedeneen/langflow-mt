from lfx.template.frontend_node.base import FrontendNode


class TestFrontendNodeVersioning:
    def test_defaults(self):
        node = FrontendNode(base_classes=["Foo"], template={"type_name": "Foo", "fields": []})
        assert node.version == 0
        assert node.changelog == []

    def test_serialize_roundtrip(self):
        node = FrontendNode(
            base_classes=["Foo"],
            template={"type_name": "Foo", "fields": []},
            version=3,
            changelog=[
                {"version": 3, "changes": "c3", "notes": "n3"},
                {"version": 2, "changes": "c2", "notes": None},
            ],
        )
        dumped = node.to_dict()
        # `to_dict` wraps under `name`; grab the inner dict
        inner = next(iter(dumped.values()))
        assert inner["version"] == 3
        assert inner["changelog"] == [
            {"version": 3, "changes": "c3", "notes": "n3"},
            {"version": 2, "changes": "c2", "notes": None},
        ]
