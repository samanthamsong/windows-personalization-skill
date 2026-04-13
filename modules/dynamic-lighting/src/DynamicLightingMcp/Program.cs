using System.Reflection;
using DynamicLightingMcp;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;

// Start the companion window on an STA thread (required for LampArray access)
var lightingWindow = new LightingWindow();
lightingWindow.Start();

var builder = Host.CreateApplicationBuilder(args);

// MCP uses stdio for JSON-RPC — all logging must go to stderr, not stdout
builder.Logging.ClearProviders();
builder.Logging.AddConsole(options => options.LogToStandardErrorThreshold = LogLevel.Trace);

builder.Services.AddSingleton(lightingWindow);
builder.Services.AddSingleton<LampArrayService>();
builder.Services.AddSingleton<EffectEngine>();

builder.Services
	.AddMcpServer()
	.WithStdioServerTransport()
	.WithToolsFromAssembly(Assembly.GetExecutingAssembly());

var host = builder.Build();

_ = host.Services.GetRequiredService<LampArrayService>();
var effectEngine = host.Services.GetRequiredService<EffectEngine>();
effectEngine.SetWindow(lightingWindow);

host.Services
    .GetRequiredService<IHostApplicationLifetime>()
    .ApplicationStopping
    .Register(() =>
    {
        effectEngine.StopAllEffects();
        lightingWindow.Dispose();
    });

await host.RunAsync();
