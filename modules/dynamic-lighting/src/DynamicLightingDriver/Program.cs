using DynamicLightingDriver;

// Start the companion window on an STA thread (required for LampArray access)
var lightingWindow = new LightingWindow();
lightingWindow.Start();

var lampArrayService = new LampArrayService();
var effectEngine = new EffectEngine();
effectEngine.SetWindow(lightingWindow);

// Wait for device discovery
await Task.Delay(2000);

var handler = new CommandHandler(lampArrayService, effectEngine, lightingWindow);

// Signal ready
Console.Error.WriteLine("DynamicLightingDriver ready");
Console.Out.WriteLine("READY");
Console.Out.Flush();

// Read commands from stdin, write responses to stdout
string? line;
while ((line = Console.In.ReadLine()) != null)
{
    if (string.IsNullOrWhiteSpace(line))
        continue;

    var response = await handler.HandleAsync(line);
    Console.Out.WriteLine(response);
    Console.Out.Flush();

    if (response == "QUIT")
        break;
}

effectEngine.StopAllEffects();
lightingWindow.Dispose();
lampArrayService.Dispose();
