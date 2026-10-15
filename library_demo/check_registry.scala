import isabelle._
import isabelle.pide.mcp._

@main def check_dynamic_tools(): Unit = {
  def tool(name: String): PIDE_MCP_Tool = new PIDE_MCP_Tool(name) {
    def description = this.name
    def input_schema = JSON_Object("type" -> "object")
    def handle(s: PIDE_MCP_Sessions, a: JSON.Object.T, p: Progress) =
      PIDE_MCP_Tool_Result.Res("ok")
  }
  val hooks = Isabelle_System.make_services(classOf[PIDE_MCP_Session_Hooks])
  assert(hooks.exists(_.name == "shared ML tools"), "ML session hook is not registered")
  val exposed = PIDE_MCP_Tool_Util.make_tool_table().keySet
  assert(!exposed.contains("demo_ml_catalogue") && !exposed.contains("demo_ml_invoke"))
  val fixed = tool("fixed")
  val sessions = new PIDE_MCP_Sessions(Map("fixed" -> fixed),
    Logger.make_progress(new Progress), new Progress, Options.init())
  // No prover is accessed: this token tests registry ownership only.
  val owner = null.asInstanceOf[PIDE_MCP_Session]
  var changes = 0
  sessions.on_tools_changed(() => { changes += 1 })
  def rejected(body: => Unit): Unit = {
    val result = Exn.capture(body)
    assert(result.isInstanceOf[Exn.Exn[_]], result)
    assert(sessions.available_tool_table.keySet == Set("fixed"))
    assert(changes == 0)
  }
  rejected(sessions.publish_tools(owner, List(tool("fixed"))))
  rejected(sessions.publish_tools(owner, List(tool("duplicate"), tool("duplicate"))))
  sessions.publish_tools(owner, List(tool("ML.example")))
  assert(sessions.available_tool_table.keySet == Set("fixed", "ML.example"))
  assert(changes == 1)
  sessions.withdraw_tools(owner)
  assert(sessions.available_tool_table.keySet == Set("fixed"))
  assert(changes == 2)
  sessions.withdraw_tools(owner)
  assert(changes == 2)
  println("PASS: collisions are atomic; publication, withdrawal, and notifications")
}
