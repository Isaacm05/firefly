using System;
using System.IO;
using System.Windows;
using System.Windows.Threading;

namespace Firefly.Client;

public partial class App : Application
{
    protected override void OnStartup(StartupEventArgs e)
    {
        DispatcherUnhandledException += (_, args) =>
        {
            File.WriteAllText(Path.Combine(Path.GetTempPath(), "firefly-crash.log"), args.Exception.ToString());
        };
        base.OnStartup(e);
    }
}
