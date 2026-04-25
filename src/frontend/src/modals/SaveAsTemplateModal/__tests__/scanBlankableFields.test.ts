import { describe, it, expect } from "@jest/globals";
import { scanBlankableFields, type BlankableFieldInfo } from "../scanBlankableFields";

function flowWithField(fieldName: string, field: Record<string, unknown>) {
  return {
    nodes: [
      {
        id: "Node-abc",
        data: {
          type: "TestComponent",
          node: {
            display_name: "Test Component",
            template: { [fieldName]: field },
          },
        },
      },
    ],
    edges: [],
  };
}

describe("scanBlankableFields", () => {
  it("identifies SecretStrInput with auto_promote", () => {
    const flow = flowWithField("api_key", {
      _input_type: "SecretStrInput",
      auto_promote: true,
      password: true,
      value: "sk-plaintext",
      display_name: "API Key",
    });
    const result = scanBlankableFields(flow);
    expect(result).toHaveLength(1);
    expect(result[0]).toEqual({
      node_id: "Node-abc",
      field_name: "api_key",
      component_display_name: "Test Component",
      field_display_name: "API Key",
    });
  });

  it("identifies TextFileSecretInput", () => {
    const flow = flowWithField("cert_pem", {
      _input_type: "TextFileSecretInput",
      value: "-----BEGIN CERTIFICATE-----\\nAAA\\n-----END CERTIFICATE-----\\n",
    });
    expect(scanBlankableFields(flow)).toHaveLength(1);
  });

  it("identifies MultilineSecretInput", () => {
    const flow = flowWithField("token", {
      _input_type: "MultilineSecretInput",
      value: "eyJhbGci...",
    });
    expect(scanBlankableFields(flow)).toHaveLength(1);
  });

  it("identifies password:true fields regardless of input type", () => {
    const flow = flowWithField("legacy_secret", {
      _input_type: "StrInput",
      password: true,
      value: "old-secret",
    });
    expect(scanBlankableFields(flow)).toHaveLength(1);
  });

  it("identifies values starting with __autosecret_", () => {
    const flow = flowWithField("cert_pem", {
      _input_type: "TextFileSecretInput",
      value: "__autosecret_flow-xyz_Node-abc_cert_pem",
    });
    expect(scanBlankableFields(flow)).toHaveLength(1);
  });

  it("leaves normal text fields out", () => {
    const flow = flowWithField("url_input", {
      _input_type: "MessageTextInput",
      value: "https://example.com",
    });
    expect(scanBlankableFields(flow)).toHaveLength(0);
  });

  it("does NOT mutate the input flow", () => {
    const flow = flowWithField("api_key", {
      _input_type: "SecretStrInput",
      auto_promote: true,
      value: "sk-plaintext",
    });
    const originalValue = flow.nodes[0].data.node.template.api_key.value;
    scanBlankableFields(flow);
    expect(flow.nodes[0].data.node.template.api_key.value).toBe(originalValue);
  });

  it("falls back to field_name when field has no display_name", () => {
    const flow = flowWithField("my_field", {
      _input_type: "SecretStrInput",
      auto_promote: true,
      value: "v",
      // no display_name
    });
    const result = scanBlankableFields(flow);
    expect(result[0].field_display_name).toBe("my_field");
  });

  it("returns entries from multiple nodes", () => {
    const flow = {
      nodes: [
        {
          id: "Node-1",
          data: {
            type: "A",
            node: {
              display_name: "A",
              template: {
                k: {
                  _input_type: "SecretStrInput",
                  auto_promote: true,
                  value: "x",
                  display_name: "K",
                },
              },
            },
          },
        },
        {
          id: "Node-2",
          data: {
            type: "B",
            node: {
              display_name: "B",
              template: {
                p: { _input_type: "StrInput", password: true, value: "y", display_name: "P" },
              },
            },
          },
        },
      ],
      edges: [],
    };
    const result = scanBlankableFields(flow);
    expect(result.map((r) => r.node_id).sort()).toEqual(["Node-1", "Node-2"]);
  });

  it("skips malformed nodes gracefully", () => {
    const flow = {
      nodes: [
        null,
        { id: "no-data" },
        {
          id: "Node-ok",
          data: {
            node: {
              display_name: "Ok",
              template: {
                k: { _input_type: "SecretStrInput", auto_promote: true, value: "x" },
              },
            },
          },
        },
      ],
      edges: [],
    };
    const result = scanBlankableFields(flow as any);
    expect(result).toHaveLength(1);
    expect(result[0].node_id).toBe("Node-ok");
  });
});
